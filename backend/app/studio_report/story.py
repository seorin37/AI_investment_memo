"""주간보고서 LLM 문장 — 검사 + 대체 문장 (2026-11-23, docs/weekly-report-plan.md 5장).

- 종목마다 1번: story(흐름 2~3문장) + issues(이번 주 이슈 정리 7~8문장). 소식이 0건이면 부르지 않는다.
- 국내 증시 칸 1번: summary(시황 7~8문장) + flow(날짜별 3~5줄) — market.py.
- 검사: 숫자는 입력에 있는 것만 · [번호]는 입력 소식 번호만 · 금지 표현(권유·예측·평가) · 출처 없는 원인 금지 · 문장 수·길이.
- 실패하면 고칠 점을 알려 주고 한 번 다시 부른다. 또 실패하면 story는 코드 문장, issues는 빈 값(화면에서 숨김).
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from functools import lru_cache
from typing import Callable

import requests

from pipelines.common.config import resolve_path

STOCK_PROMPT = "configs/report_stock_prompt.md"
MEMO_PROMPT = "configs/report_memo_prompt.md"
VERIFY_PROMPT = "configs/report_verify_prompt.md"
# 정기보고서는 '공시가 나왔다'는 말 말고 쓸 내용이 없어 LLM 입력에서 뺀다 (화면 소식 목록에는 남는다)
PERIODIC = re.compile(r"(분기|반기|사업)보고서")
URL = "https://api.openai.com/v1/chat/completions"
WEEKDAYS = "월화수목금토일"
SNIPPET_CHARS = 300

SUGGEST_ITEM = {"type": "object", "additionalProperties": False,
                "properties": {"text": {"type": "string"}, "memo_title": {"type": "string"}, "memo_body": {"type": "string"},
                               "refs": {"type": "array", "items": {"type": "integer"}}},
                "required": ["text", "memo_title", "memo_body", "refs"]}
SCHEMA_STOCK = {"name": "report_stock", "strict": True,
                "schema": {"type": "object", "additionalProperties": False,
                           "properties": {"story": {"type": "string"}, "issues": {"type": "string"},
                                          "suggest": {"type": "array", "items": SUGGEST_ITEM}},
                           "required": ["story", "issues", "suggest"]}}
# 다음에 추적해 볼 메모 제안 (2026-11-24): 예측·권유처럼 읽히는 말은 제안에서도 뺀다
SUGGEST_BANNED = re.compile(r"전망|오를|내릴|반등|상승할|하락할|기대|목표가|목표주가|매수|매도|사야|팔아|사도|담아|손절|익절|추천")
SUGGEST_ASK = re.compile(r"알려|챙겨|나오면|확인")

BANNED = ["사세요", "파세요", "매수 기회", "매도 기회", "담을 때", "손절하", "호재", "악재", "긍정적", "부정적", "저평가", "고평가",
          "유망", "유리", "불리", "확실히", "반드시", "틀림없이", "추천", "수혜"]
BANNED_PATTERNS = [
    r"(오를|내릴|올라갈|떨어질|상승할|하락할|회복될|반등할)\s*(거|것|가능성|듯)",
    r"가능성이?\s*(높|큽|커)", r"(전망|예상|추정|관측|기대)(돼요|되어요|됩니다|이에요|입니다)",
    r"것으로\s*(보여요|보입니다|보인다)",
]
# 원인 붙이기. 같은 문장에 출처(말한 사람)가 있으면 허용한다
CAUSE = re.compile(r"때문|덕분|덕에|영향으로|영향을\s*받|여파|힘입|탓에|탓으로|견인|이끌")
ATTRIB = re.compile(r"보도했|전했|밝혔|분석했|설명했|말했|진단했|따르면|평가했|주장했|지적했|내다봤|봤다고|분석이에요")   # 말한 사람이 주어인 문장 (명사 "보도"만으로는 안 됨)
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
REF = re.compile(r"\[(\d+)\]")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

LLMCall = Callable[..., dict]

SCHEMA_VERIFY = {"name": "report_verify", "strict": True,
                 "schema": {"type": "object", "additionalProperties": False,
                            "properties": {"results": {"type": "array", "items": {
                                "type": "object", "additionalProperties": False,
                                "properties": {"i": {"type": "integer"}, "ok": {"type": "boolean"}, "why": {"type": "string"}},
                                "required": ["i", "ok", "why"]}}},
                            "required": ["results"]}}


@lru_cache(maxsize=4)
def load_prompt(path: str) -> str:
    text = resolve_path(path).read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()


def md(d: date) -> str:
    return f"{d.month:02d}.{d.day:02d}"


# 문장 끝: "~요." "~요[3]." "~요[3]" "~다." (마침표 없이 번호로 끝나는 문장도 센다)
SENT_END = re.compile(r"(?:(?:(?<![주필중수])요|니다|다(?=[\[.!?]))[.!?]?(?:\[\d+\])*[.!?]?|[.!?](?:\[\d+\])*)(?=\s|$)")   # "~요[3]." "~요.[3]" 둘 다 끝. "주요·필요·중요·수요"는 아님


def sentences(text: str) -> list[str]:
    out, start = [], 0
    t = (text or "").strip()
    for m in SENT_END.finditer(t):
        piece = t[start:m.end()].strip()
        if piece:
            out.append(piece)
        start = m.end()
    rest = t[start:].strip()
    if rest:
        out.append(rest)
    return out


def price_lines(p: dict) -> list[str]:
    """주가 줄. 등락률은 전부 코드가 계산해 적는다 (LLM이 계산하지 않게)."""
    dates: list[date] = p["trade_dates"]
    lines = ["주가 (시세 DB, 등락률은 코드 계산):", f"- 지난주 마지막 종가 {int(round(p['prev'])):,}원"]
    before = p["prev"]
    for d, c in zip(dates, p["closes"]):
        lines.append(f"- {md(d)}({WEEKDAYS[d.weekday()]}) 종가 {int(round(c)):,}원 (전날보다 {(c - before) / before * 100:+.1f}%)")
        before = c
    lines.append(f"- 이 주의 마지막 거래일(시세 기준)은 {md(dates[-1])}이에요")
    lines.append(f"- 주간: {md(dates[-1])} 종가 {int(round(p['close'])):,}원, 지난주 마지막 종가보다 {p['pct']:+.1f}%")
    return lines


def item_line(it) -> str:
    head = f"[{it.no}] {md(it.day)}({WEEKDAYS[it.day.weekday()]}) · {it.kind} · {it.src or '뉴스'} · {it.title}"
    if getattr(it, "buzz", 0) >= 2:                  # 여러 매체가 다룬 소식 (중요도 힌트)
        head += f" · 같은 날 비슷한 기사 {it.buzz}건"
    snip = (getattr(it, "snippet", "") or "").strip()
    return head + (f"\n    내용: {snip[:SNIPPET_CHARS]}" if snip else "")


def input_text(name: str, p: dict, items: list, extra: list[str] | None = None) -> str:
    lines = [f"종목: {name}", *price_lines(p), *(extra or []), "소식 (번호 · 날짜 · 종류 · 출처 · 제목 / 내용은 본문 앞부분):"]
    lines += [item_line(it) for it in items]
    return "\n".join(lines)


def _num_set(text: str) -> set[str]:
    out = set()
    for n in NUM.findall(text):
        v = n.replace(",", "")
        out.add(v)
        if "." in v:
            out.add(v.rstrip("0").rstrip("."))
    return out


def check_text(text: str, source: str, nos: set[int], min_s: int, max_s: int, max_chars: int, label: str,
               need_refs: bool = True) -> list[str]:
    """문제 목록 (비어 있으면 통과). label은 고칠 점 안내에 붙인다 (story·issues·summary)."""
    problems = []
    s = (text or "").strip()
    sents = sentences(s)
    if not (min_s <= len(sents) <= max_s) or len(s) > max_chars:
        problems.append(f"{label}: 문장 {len(sents)}개·{len(s)}자 ({min_s}~{max_s}문장, {max_chars}자 안으로)")
    refs = {int(r) for r in REF.findall(s)}
    if refs - nos:
        problems.append(f"{label}: 입력에 없는 번호 {sorted(refs - nos)}")
    if need_refs and nos and not refs:
        problems.append(f"{label}: 소식 번호가 하나도 없음")
    allowed = _num_set(source) | {str(n) for n in nos}
    bad = sorted(v for v in _num_set(REF.sub("", s)) if v not in allowed)
    if bad:
        problems.append(f"{label}: 입력에 없는 숫자 {bad}")
    hit = [w for w in BANNED if w in s] + [m.group(0) for pat in BANNED_PATTERNS for m in re.finditer(pat, s)]
    if hit:
        problems.append(f"{label}: 금지 표현 {hit}")
    for sent in sents:
        c = CAUSE.search(sent)
        if c and not ATTRIB.search(sent):
            problems.append(f"{label}: 출처 없이 원인을 붙임 '{c.group(0)}' (기사에 있으면 출처를 주어로)")
            break
    return problems


def check_story(story: str, source: str, nos: set[int]) -> list[str]:
    return check_text(story, source, nos, 1, 3, 320, "story")


def check_issues(issues: str, source: str, nos: set[int]) -> list[str]:
    return check_text(issues, source, nos, 3, 9, 1000, "issues")


def check_suggestion(s: dict, nos: set[int]) -> list[str]:
    """제안 하나의 문제 목록 (비어 있으면 통과). 걸린 제안만 빼고 보고서는 그대로 둔다."""
    text, title, body = (s.get("text") or "").strip(), (s.get("memo_title") or "").strip(), (s.get("memo_body") or "").strip()
    refs = [r for r in (s.get("refs") or []) if isinstance(r, int)]
    probs = []
    if not 6 <= len(text) <= 60:
        probs.append("text 길이")
    if not 2 <= len(title) <= 20:
        probs.append("memo_title 길이")
    if not 8 <= len(body) <= 140:
        probs.append("memo_body 길이")
    if not refs or any(r not in nos for r in refs):
        probs.append("refs")
    joined = " ".join((text, title, body))
    if SUGGEST_BANNED.search(joined) or any(w in joined for w in BANNED):
        probs.append("금지 표현")
    if not SUGGEST_ASK.search(body):
        probs.append("memo_body가 추적 요청으로 끝나지 않음")
    return probs


def clean_suggestions(raw, nos: set[int], limit: int = 2) -> list[dict]:
    out = []
    for s in raw or []:
        if isinstance(s, dict) and not check_suggestion(s, nos):
            out.append({"text": s["text"].strip(), "memo_title": s["memo_title"].strip(), "memo_body": s["memo_body"].strip(),
                        "refs": sorted({r for r in s["refs"] if isinstance(r, int)})})
        if len(out) >= limit:
            break
    return out


def openai_call(messages: list[dict], schema: dict = SCHEMA_STOCK, model: str | None = None) -> dict:
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("LLM 키가 설정되지 않았어요")
    model = model or os.getenv("REPORT_MODEL") or os.getenv("LLM_MODEL") or "gpt-4.1-mini"
    body = {"model": model, "messages": messages, "response_format": {"type": "json_schema", "json_schema": schema}}
    res = requests.post(URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=float(os.getenv("REPORT_TIMEOUT", "90")))
    if res.status_code != 200:
        raise RuntimeError(f"OpenAI HTTP {res.status_code}")
    data = res.json()
    msg = data["choices"][0]["message"]
    if msg.get("refusal"):
        raise RuntimeError("LLM이 답을 거절했어요")
    out = json.loads(msg["content"])
    u = data.get("usage") or {}
    out["_usage"] = {"input": u.get("prompt_tokens") or 0, "output": u.get("completion_tokens") or 0}
    return out


def ask(call: LLMCall, prompt: str, source: str, schema: dict, check: Callable[[dict], list[str]], tries: int = 2):
    """LLM을 부르고 검사한다. (통과한 답 또는 None, 메타 {tries, problems, usage})."""
    msgs = [{"role": "system", "content": load_prompt(prompt)}, {"role": "user", "content": source}]
    usage = {"input": 0, "output": 0}
    problems: list[str] = []
    for k in range(1, tries + 1):
        try:
            out = call(msgs, schema)
        except TypeError:                                  # 스키마를 받지 않는 호출(테스트 가짜 등)
            out = call(msgs)
        except Exception as exc:
            problems = [f"호출 실패 {type(exc).__name__}"]
            continue
        for key in usage:
            usage[key] += (out.get("_usage") or {}).get(key) or 0
        problems = check(out)
        if not problems:
            return out, {"tries": k, "problems": [], "usage": usage}
        shown = {kk: v for kk, v in out.items() if not kk.startswith("_")}
        msgs = msgs + [{"role": "assistant", "content": json.dumps(shown, ensure_ascii=False)},
                       {"role": "user", "content": "검사에서 고칠 점: " + " / ".join(problems) + ". 원칙대로 다시 써 주세요."}]
    return None, {"tries": tries, "problems": problems, "usage": usage}


def verify_model() -> str:
    return os.getenv("REPORT_VERIFY_MODEL") or "gpt-6.1-terra"


def verify_texts(call: LLMCall, source: str, texts: dict[str, str]) -> tuple[dict[str, str], list[dict], dict]:
    """문장마다 근거와 대조해(검수 LLM 1번) 뒷받침되지 않는 문장을 뺀다. 문단(빈 줄)은 유지한다.
    (고친 글들, 뺀 문장 [{field, text, why}], usage). 검수 호출이 실패하면 그대로 둔다 (usage에 failed 표시)."""
    numbered: list[tuple[str, int, str]] = []          # (필드, 문단 번호, 문장)
    for field, text in texts.items():
        for k, para in enumerate((text or "").split("\n\n")):
            for sent in sentences(para):
                numbered.append((field, k, sent))
    usage = {"input": 0, "output": 0, "failed": False}
    if not numbered:
        return texts, [], usage
    listing = "\n".join(f"{i}. {sent}" for i, (_f, _k, sent) in enumerate(numbered, 1))
    msgs = [{"role": "system", "content": load_prompt(VERIFY_PROMPT)},
            {"role": "user", "content": f"[자료]\n{source}\n\n[문장 목록]\n{listing}"}]
    try:
        try:
            out = call(msgs, SCHEMA_VERIFY, verify_model())
        except TypeError:                                  # 모델·스키마를 받지 않는 호출(테스트 가짜 등)
            out = call(msgs)
    except Exception:
        usage["failed"] = True
        return texts, [], usage
    for key in ("input", "output"):
        usage[key] = (out.get("_usage") or {}).get(key) or 0
    bad = {int(r["i"]): r.get("why", "") for r in out.get("results") or [] if not r.get("ok", True)}
    removed = [{"field": f, "text": sent, "why": bad[i]} for i, (f, _k, sent) in enumerate(numbered, 1) if i in bad]
    kept: dict[str, dict[int, list[str]]] = {}
    for i, (f, k, sent) in enumerate(numbered, 1):
        if i not in bad:
            kept.setdefault(f, {}).setdefault(k, []).append(sent)
    cleaned = {f: "\n\n".join(" ".join(ss) for _k, ss in sorted(kept.get(f, {}).items())) for f in texts}
    return cleaned, removed, usage


def llm_stock(name: str, p: dict, items: list, call: LLMCall, fallback: str, extra: list[str] | None = None, verify: bool = True):
    """(story, issues, 메타 {source, tries, problems, usage, removed}). issues가 검사에 걸리면 story만 살린다.
    검사를 통과하면 검수 LLM으로 문장마다 근거를 대조해 뒷받침되지 않는 문장을 뺀다 (story가 다 빠지면 코드 문장)."""
    items = [it for it in items if not (it.kind == "공시" and PERIODIC.search(it.title or ""))]
    if not items:
        return fallback, "", {"source": "code", "tries": 0, "problems": [], "usage": {"input": 0, "output": 0}}
    source = input_text(name, p, items, extra)
    nos = {it.no for it in items}

    # 주말(토·일)에 여러 매체가 다룬 소식은 이슈 정리에서 빠뜨리지 않는다 (월~금만 쓰고 주말을 건너뛰는 일이 있었다, 2026-11-23)
    must = sorted({it.no for it in items if it.kind == "뉴스" and it.day.weekday() >= 5 and getattr(it, "buzz", 0) >= 2})

    def check(out: dict) -> list[str]:
        probs = check_story(out.get("story", ""), source, nos) + check_issues(out.get("issues", ""), source, nos)
        used = {int(r) for r in REF.findall(out.get("issues", ""))}
        if must and not (used & set(must)):
            probs.append("issues: 주말에 여러 매체가 다룬 소식 " + "".join(f"[{n}]" for n in must)
                         + "을 다루지 않음 (출처를 주어로, 기사에 적힌 진행 상태까지 한 주제로 쓰기)")
        return probs
    out, meta = ask(call, STOCK_PROMPT, source, SCHEMA_STOCK, check)
    if out is None:
        return fallback, "", {"source": "code", **meta, "removed": []}
    story, issues = out["story"].strip(), out["issues"].strip()
    meta["suggest"] = clean_suggestions(out.get("suggest"), nos)
    removed: list[dict] = []
    if verify:
        cleaned, removed, vu = verify_texts(call, source, {"story": story, "issues": issues})
        meta["usage"] = {k: meta["usage"][k] + vu[k] for k in ("input", "output")}
        meta["verify_failed"] = vu["failed"]
        story = cleaned["story"] or fallback
        issues = cleaned["issues"] if len(sentences(cleaned["issues"].replace("\n\n", " "))) >= 2 else ""
    return story, issues, {"source": "llm", **meta, "removed": removed}


SCHEMA_MEMO = {"name": "report_memo", "strict": True,
               "schema": {"type": "object", "additionalProperties": False,
                          "properties": {"digest": {"type": "string"}}, "required": ["digest"]}}


def memo_input(name: str, memos: list[dict]) -> str:
    k = sum(1 for m in memos if m["cards"])
    lines = [f"종목: {name}", f"메모 {len(memos)}개, 그중 이번 주 새 소식이 붙은 메모 {k}개:"]
    for m in memos:
        lines.append(f"- 메모 '{m['title']}' ({m['meta']})")
        for c in m["cards"]:
            refs = "".join(f"[{r}]" for r in c["refs"])
            lines.append(f"    {c['date']} {c['kind']} · {c['title']} · {c['text']} {refs}".rstrip())
        lines += [f"    {s}" for s in m.get("status") or []]
        if not m["cards"] and not m.get("status"):
            lines.append("    이번 주 새 소식 없음")
    return "\n".join(lines)


def llm_memo_digest(name: str, memos: list[dict], call: LLMCall, fallback: str):
    """(정리 2~3문장, 메타). 카드도 가격 상태도 없으면 LLM 없이 코드 문장 (2026-11-24)."""
    if not any(m["cards"] for m in memos):                    # 카드가 없으면 코드 문장 (가격 상태는 코드가 붙임)
        return fallback, {"source": "code", "tries": 0, "problems": [], "usage": {"input": 0, "output": 0}}
    source = memo_input(name, memos)
    nos = {r for m in memos for c in m["cards"] for r in c["refs"]}
    out, meta = ask(call, MEMO_PROMPT, source, SCHEMA_MEMO,
                    lambda o: check_text(o.get("digest", ""), source, nos, 1, 3, 340, "digest", need_refs=bool(nos)))
    if out is None:
        return fallback, {"source": "code", **meta}
    return out["digest"].strip(), {"source": "llm", **meta}


def llm_story(name: str, p: dict, items: list, call: LLMCall, fallback: str, tries: int = 2):
    """(story, 메타) — 예전 이름 (1단계 테스트 호환)."""
    story, _issues, meta = llm_stock(name, p, items, call, fallback)
    return story, meta
