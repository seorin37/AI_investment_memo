"""대본 LLM 출력 형식(OpenAI 구조화 출력, strict)과 받은 뒤의 검사.

검사에 걸린 문제는 사람이 읽는 문장으로 돌려준다 (재시도 때 LLM에 그대로 준다).
숫자 검사는 업데이트 카드 검사(pipelines.updates.checks)의 숫자 읽기를 그대로 쓴다: 대본 한 줄의 숫자는
그 구간(종목)의 브리프에 있는 숫자여야 한다. 소수는 반올림한 값(소수 한 자리·정수)도 인정한다.
"""
from __future__ import annotations

import re
from functools import lru_cache

from .collect import Brief
from .prompt import build_user, config, target_chars

KINDS = ["opening", "market", "stock", "no_news", "closing"]
AUDIO_SCHEMA = {
    "name": "audio_script",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["title", "segments"],
        "properties": {
            "title": {"type": "string"},
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "stock_code", "lines"],
                    "properties": {
                        "kind": {"type": "string", "enum": KINDS},
                        "stock_code": {"type": "string"},
                        "lines": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["speaker", "text", "refs"],
                                "properties": {
                                    "speaker": {"type": "string", "enum": ["A", "B"]},
                                    "text": {"type": "string"},
                                    "refs": {"type": "array", "items": {"type": "string"}},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}

# 업데이트 카드 금지 사전·시제 패턴(configs/updates.yaml)에 더해 오디오에서 따로 막는 말
EXTRA_BANNED = [
    (re.compile(r"매수|매도"), "매수·매도 표현 (자사주·자기주식 매수 같은 공시 사실은 괜찮아요)"),
    (re.compile(r"추천|사야|팔아야|지금이\s*기회|기회(예요|입니다)"), "권유·추천 표현"),
    (re.compile(r"목표\s*주가"), "목표주가"),
    (re.compile(r"수혜"), "'수혜' 표현"),
    (re.compile(r"급등|급락|폭등|폭락"), "급등·급락 표현"),
    (re.compile(r"장중"), "'장중' 표현 (종가 기준으로만 말해요)"),
    (re.compile(r"주가[^.?!]{0,12}(오를|올라갈|내릴|떨어질|상승할|하락할)"), "주가 방향 예측"),
]
FACT_OK = re.compile(r"(자사주|자기주식|지분|주식)\s*(을|를)?\s*(매수|매도)")


@lru_cache(maxsize=1)
def _updates_rules() -> tuple[list[str], list[re.Pattern]]:
    from pipelines.common.config import load_config
    cfg = load_config("configs/updates.yaml")
    return list(cfg.get("banned") or []), [re.compile(p) for p in (cfg.get("topic") or {}).get("banned_patterns") or []]


def banned_hits(text: str) -> list[str]:
    from pipelines.updates.checks import ATTRIBUTION, attributed_forecast
    words, patterns = _updates_rules()
    hits = [f"금지 표현 '{w}'" for w in words if w in text]
    sentences = [s for s in re.split(r"(?<=[.!?요])\s+", text) if s.strip()]
    for s in sentences:
        reported = any(a in s for a in ATTRIBUTION) or attributed_forecast(s, headline=True) or "보도했" in s
        if not reported and any(p.search(s) for p in patterns):
            hits.append(f"주체 없는 전망·예측 표현 (\"{s[:30]}\")")
    clean = FACT_OK.sub(" ", text)
    hits += [label for p, label in EXTRA_BANNED if p.search(clean)]
    return hits


def _allowed_numbers(texts: list[str]) -> set[float]:
    from pipelines.updates.checks import all_numbers
    out: set[float] = set()
    for t in texts:
        for v in all_numbers(t):
            out.add(round(v, 6))
            if not float(v).is_integer():
                out.add(round(v, 1))
                out.add(float(round(v)))
    return out


def unknown_numbers(text: str, allowed: set[float]) -> list[float]:
    from pipelines.updates.checks import numbers
    return sorted(v for v in numbers(text) if round(v, 6) not in allowed)


def stock_block(brief: Brief, code: str) -> str:
    """브리프 글에서 그 종목 부분만 (숫자 검사용)."""
    full = build_user(brief)
    st = brief.stock(code)
    if st is None:
        return ""
    head = f"] {st.name} ({st.code})"
    start = full.find(head)
    if start < 0:
        return ""
    nxt = full.find("\n[종목 ", start)
    return full[full.rfind("[종목", 0, start):nxt if nxt > 0 else len(full)]


def name_variants(name: str) -> set[str]:
    pron = config().get("pronounce") or {}
    out = {name, pron.get(name, name)}
    out |= {k for k, v in pron.items() if v == name or k == name}
    if name.upper() == "NAVER":
        out.add("네이버")
    return {v for v in out if v}


def check(raw: dict, brief: Brief, cfg: dict | None = None) -> list[str]:
    cfg = cfg or config()
    s = cfg["script"]
    errors: list[str] = []
    segs = raw.get("segments") or []
    if not segs:
        return ["segments가 비어 있어요"]
    kinds = [g.get("kind") for g in segs]
    if kinds[0] != "opening":
        errors.append("첫 구간은 opening이어야 해요")
    if kinds[-1] != "closing":
        errors.append("마지막 구간은 closing이어야 해요")
    if "market" in kinds and not brief.market:
        errors.append("입력에 [증시]가 없는데 market 구간을 썼어요")
    want = [st.code for st in brief.news_stocks]
    got = [g.get("stock_code") for g in segs if g.get("kind") == "stock"]
    if sorted(got) != sorted(want):
        errors.append(f"stock 구간은 새 소식이 있는 종목 {want}마다 정확히 하나씩이어야 해요 (지금 {got})")
    if brief.quiet_stocks and "no_news" not in kinds:
        errors.append("새 소식이 없는 종목이 있는데 no_news 구간이 없어요")
    if not brief.quiet_stocks and "no_news" in kinds:
        errors.append("새 소식이 없는 종목이 없는데 no_news 구간을 썼어요")

    whole = _allowed_numbers([build_user(brief)])
    all_uids = {c.uid for st in brief.stocks for c in st.cards}
    cited: set[str] = set()
    run_speaker, run = "", 0
    total = 0
    for g in segs:
        kind, code, lines = g.get("kind"), g.get("stock_code") or "", g.get("lines") or []
        if not lines:
            errors.append(f"{kind} {code} 구간에 줄이 없어요")
            continue
        st = brief.stock(code) if kind == "stock" else None
        own = {c.uid for c in st.cards} if st else all_uids
        allowed = (_allowed_numbers([stock_block(brief, code), f"{brief.start} {brief.end}"]) if st else whole)
        text_all = " ".join(str(line.get("text") or "") for line in lines)
        if st and not any(v in text_all for v in name_variants(st.name)):
            errors.append(f"{st.name} 구간에 종목 이름이 한 번도 나오지 않아요")
        if kind == "no_news":
            missing = [q.name for q in brief.quiet_stocks if not any(v in text_all for v in name_variants(q.name))]
            if missing:
                errors.append(f"no_news 구간에 {missing} 이름이 빠졌어요")
        for line in lines:
            t = str(line.get("text") or "").strip()
            total += len(t)
            if not t:
                errors.append(f"{kind} 구간에 빈 줄이 있어요")
                continue
            if len(t) > s["line_max_chars"]:
                errors.append(f"한 줄이 {len(t)}자로 길어요 ({s['line_max_chars']}자 이내): \"{t[:25]}…\"")
            sp = line.get("speaker")
            run, run_speaker = (run + 1, sp) if sp == run_speaker else (1, sp)
            if run > s["max_same_speaker"]:
                errors.append(f"진행자 {sp}가 {run}줄 이어서 말해요 (A·B를 번갈아)")
            bad_refs = [r for r in line.get("refs") or [] if r not in own]
            if bad_refs:
                errors.append(f"{kind} {code} 구간에 쓸 수 없는 참조 {bad_refs}")
            cited |= set(line.get("refs") or []) & all_uids
            for h in banned_hits(t):
                errors.append(f"{h}: \"{t[:30]}\"")
            unknown = unknown_numbers(t, allowed)
            if unknown:
                errors.append(f"입력에 없는 숫자 {[f'{v:g}' for v in unknown]}: \"{t[:30]}\"")
    missing = sorted(all_uids - cited, key=lambda u: int(u[1:]))
    if missing:
        errors.append(f"업데이트 {missing}를 한 번도 refs에 쓰지 않았어요 (모두 소개해 주세요)")
    if segs and kinds[-1] == "closing":
        last = str((segs[-1].get("lines") or [{}])[-1].get("text") or "")
        if "판단" not in last and "직접" not in last:
            errors.append("마지막 줄에 '판단은 메모와 원문을 직접 보고' 안내가 없어요")
    goal = target_chars(brief, cfg)
    if total > goal * s["over_ratio"]:
        errors.append(f"대본이 {total}자로 너무 길어요 (목표 약 {goal}자)")
    if total < goal * 0.35:
        errors.append(f"대본이 {total}자로 너무 짧아요 (목표 약 {goal}자)")
    title = str(raw.get("title") or "").strip()
    if not title or len(title) > 30:
        errors.append("title은 1~30자여야 해요")
    return list(dict.fromkeys(errors))
