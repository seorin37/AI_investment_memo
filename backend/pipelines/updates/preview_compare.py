"""두 실행(v1·v2 카드)을 항목별로 나란히 보는 미리보기 (preview_compare.html). 파일만 읽는다 (DB·LLM 없음).

    PYTHONPATH=backend python -m pipelines.updates.preview_compare results/updates/run_A results/updates/run_B \
        [--labels v1,v2] [--out results/updates/compare_A_B/preview_compare.html]

- 행 하나 = 추적 항목 하나 (메모 문장·항목 설명). 왼쪽 A, 오른쪽 B의 카드(preview.py와 같은 모양)나 카드가 없는 이유.
- 어느 한쪽에라도 카드가 있는 항목을 먼저, 그다음 둘 다 카드가 없는 항목은 접어서 보여 준다.
- 같은 메모·같은 근거라 다른 카드로 합쳐진 항목(v2 merged_items)은 "○○ 카드로 합침"으로 적는다.
- 폭이 좁으면 위아래로 쌓는다.
"""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

from .preview import CSS, EMPTY_REASON, TYPE_LABEL, _card_html, _source_line

EXTRA_CSS = """
main{max-width:1240px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 18px;align-items:start}
@media (max-width:820px){.pair{grid-template-columns:1fr}}
.item{margin:22px 0 6px;font-size:13px;color:var(--sub)}.item b{color:var(--ink);font-size:14px}
.side{font-size:11px;font-weight:700;color:var(--sub);margin:0 0 4px;letter-spacing:.04em}
.none{background:var(--card);border:1px dashed var(--line);border-radius:12px;padding:10px 14px;color:var(--sub);font-size:13px}
.sum{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--sub);margin:0 0 12px}
details.rest>summary{cursor:pointer;color:var(--sub);margin:24px 0 8px}
"""


def load(run: Path) -> dict:
    read = lambda name: [json.loads(l) for l in (run / name).read_text(encoding="utf-8").splitlines() if l.strip()] \
        if (run / name).exists() else []
    cards = read("cards.jsonl")
    refs = json.loads((run / "refs.json").read_text(encoding="utf-8")) if (run / "refs.json").exists() else {}
    outcomes = {o["item_id"]: o for o in read("outcomes.jsonl")}
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    return {"name": run.name, "cards": {c["item_id"]: c for c in cards}, "refs": refs, "outcomes": outcomes,
            "summary": summary, "items": {c["item_id"]: c for c in cards}}


def _side(run: dict, item_id: str, label: str) -> str:
    head = f'<div class="side">{escape(label)}</div>'
    card = run["cards"].get(item_id)
    if card is not None:
        return head + _card_html(card, run["refs"])
    o = run["outcomes"].get(item_id) or {}
    if o.get("merged_into"):
        return head + f'<div class="none">같은 근거라 {escape(o["merged_into"])} 카드로 합쳤어요</div>'
    why = EMPTY_REASON.get(o.get("kind", ""), o.get("kind") or "결과 없음")
    codes = f" · 검사: {', '.join(o['fail_codes'])}" if o.get("fail_codes") else ""
    return head + f'<div class="none">카드 없음 · {escape(why)}{escape(codes)}</div>'


def _meta(run: dict, label: str) -> str:
    s = run["summary"]
    return (f"<span><b>{escape(label)}</b> {escape(run['name'])} · 카드 {len(run['cards'])} · "
            f"호출 {s.get('llm_calls', '-')} · 입력 {s.get('prompt_tokens', '-')} · 출력 {s.get('output_tokens', '-')}</span>")


def build(a: dict, b: dict, labels: tuple[str, str]) -> str:
    info: dict[str, dict] = {}
    for run in (a, b):
        for iid, o in run["outcomes"].items():
            info.setdefault(iid, {"description": o.get("description", ""), "symbol": o.get("symbol", "")})
        for iid, c in run["cards"].items():
            info.setdefault(iid, {"description": c.get("description", ""), "symbol": c.get("symbol", "")}).update(
                memo=c.get("memo_text", ""), company=c.get("company_name", ""))
    with_card = [i for i in info if i in a["cards"] or i in b["cards"]]
    rest = [i for i in info if i not in with_card]

    def row(iid: str) -> str:
        x = info[iid]
        return (f'<div class="item"><b>{escape(x.get("company") or x.get("symbol") or "")} · {escape(x["description"])}</b>'
                f' ({escape(iid)}){" · 메모: " + escape(x["memo"]) if x.get("memo") else ""}</div>'
                f'<div class="pair"><div>{_side(a, iid, labels[0])}</div><div>{_side(b, iid, labels[1])}</div></div>')

    body = "".join(row(i) for i in sorted(with_card))
    rest_html = (f'<details class="rest"><summary>둘 다 카드가 없는 항목 {len(rest)}개</summary>'
                 + "".join(row(i) for i in sorted(rest)) + "</details>") if rest else ""
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>카드 v1·v2 비교</title><style>{CSS}{EXTRA_CSS}</style></head><body><main>"
            f'<h1>카드 비교 · {escape(labels[0])} / {escape(labels[1])}</h1>'
            f'<div class="sum">{_meta(a, labels[0])}{_meta(b, labels[1])}</div>'
            f'<p class="meta">카드가 있는 항목 {len(with_card)}개 · 카드를 누르면 자세히 볼 수 있어요</p>'
            f"{body}{rest_html}</main></body></html>")


# ---------------------------------------------------------------------------------------------------------------
# 두 방식 메모 단위 비교 (method_compare 결과 폴더, 2026-11-19). 한 줄에 [서린 카드] [팀원 카드] [LLM이 받은 근거]
# ---------------------------------------------------------------------------------------------------------------
METHODS = (("seorin", "서린 · 운영 설정"), ("minyi", "팀원 · updates_exp"))
REASON_KO = {
    "card": "카드", "price_unchanged": "가격 조건: 아직 조건가에 가깝지 않음", "price_changed": "가격 카드",
    "no_candidates": "후보 없음 (검색 기준을 넘는 뉴스·공시 없음)",
    "no_relevant_candidates": "관련 후보 없음 (관련성 판정에서 모두 X)",
    "llm_no_update": "새 소식 없음 (카드 작성 LLM이 no_update)", "check_failed": "코드 검사 실패",
    "verify_failed": "검수 실패", "already_shown": "이미 보여 준 소식", "not_called": "LLM을 부르지 않음",
    "call_failed": "LLM 호출 실패", "no_data": "자료 없음", "price_no_data": "주가 자료 없음",
    "ask_no_answer": "자료 없음 답 (질문에 답을 못 찾음, 사용자에게 보임)", "merged": "같은 근거라 다른 항목 카드로 합침",
}
METHODS_CSS = """
main{max-width:1500px}
.memo-row{border-top:1px solid var(--line);padding:16px 0 8px}
.memo-head{display:flex;gap:10px;flex-wrap:wrap;align-items:baseline;font-size:13px;color:var(--sub)}
.memo-head b{color:var(--ink);font-size:15px}
.memo-text{background:var(--memo);border-radius:8px;padding:8px 12px;margin:6px 0 10px;white-space:pre-wrap}
.cols{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;align-items:start}
@media (max-width:1000px){.cols{grid-template-columns:1fr}}
.colhead{font-size:11px;font-weight:700;color:var(--sub);letter-spacing:.04em;margin:0 0 6px}
.itemlab{font-size:11px;color:var(--sub);margin:10px 0 3px}
.kind{border-radius:5px;padding:0 6px;font-weight:700;margin-right:4px;background:var(--chip-d);color:var(--ink)}
.kind.ask{background:var(--chip-p)}
.vcard{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:0 0 8px}
.vcard .title{margin:4px 0 6px}
.why{background:var(--card);border:1px dashed var(--line);border-radius:12px;padding:8px 12px;color:var(--sub);font-size:13px;margin:0 0 8px}
.why .code{color:var(--warn);font-weight:700}
.why ul{margin:4px 0 0;padding-left:18px}.why li.hit{color:var(--ink)}
.anal{font-size:12px;color:var(--sub);margin:0 0 6px}
details.ev{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:0 0 8px;padding:6px 10px}
details.ev>summary{cursor:pointer;font-size:12px;color:var(--sub)}
details.ev pre{white-space:pre-wrap;font-size:12px;margin:6px 0 0;max-height:420px;overflow:auto}
details.fold>summary{cursor:pointer;font-size:12px;color:var(--sub);margin-top:8px}
.calc{font-size:13px;margin:6px 0 0}
.pick{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:10px 0 0}
.pick button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:4px 12px;font-size:13px;cursor:pointer}
.pick button[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:#fff}
.pick textarea{flex:1 1 260px;min-height:32px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);
font:13px/1.4 inherit;padding:6px 8px}
.top{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin:8px 0 14px}
.top .box{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;font-size:13px}
.top table{border-collapse:collapse;width:100%}.top td{padding:2px 4px;border-bottom:1px solid var(--line)}
.top td.n{text-align:right;font-variant-numeric:tabular-nums}
.bar{position:sticky;top:0;z-index:2;background:var(--bg);padding:8px 0;display:flex;gap:14px;flex-wrap:wrap;align-items:center;
border-bottom:1px solid var(--line);font-size:13px}
.bar button{border:1px solid var(--accent);background:var(--accent);color:#fff;border-radius:8px;padding:5px 12px;cursor:pointer}
.same{font-size:11px;color:var(--sub);border:1px solid var(--line);border-radius:6px;padding:0 6px}
"""
METHODS_JS = """
const KEY='method_compare_picks_'+document.body.dataset.run;
let picks={};try{picks=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){picks={}}
function save(){try{localStorage.setItem(KEY,JSON.stringify(picks))}catch(e){}}
document.querySelectorAll('.memo-row').forEach(row=>{
  const id=row.dataset.memo,p=picks[id]||{};const btns=row.querySelectorAll('.pick button'),note=row.querySelector('.pick textarea');
  btns.forEach(b=>{b.setAttribute('aria-pressed',b.dataset.v===p.choice);b.addEventListener('click',()=>{
    const cur=(picks[id]||{});cur.choice=cur.choice===b.dataset.v?'':b.dataset.v;picks[id]=cur;
    btns.forEach(x=>x.setAttribute('aria-pressed',x.dataset.v===cur.choice));save();count()})});
  note.value=p.note||'';note.addEventListener('input',()=>{const cur=(picks[id]||{});cur.note=note.value;picks[id]=cur;save()});
});
function count(){const n=Object.values(picks).filter(p=>p.choice).length;document.getElementById('picked').textContent=n}
count();
function filt(){const d=document.getElementById('diffonly').checked,x=document.getElementById('extraonly');
  const xo=x&&x.checked;document.querySelectorAll('.memo-row').forEach(r=>{
  r.hidden=(d&&r.dataset.diff!=='1')||(xo&&r.dataset.extra!=='1')})}
document.getElementById('diffonly').addEventListener('change',filt);
if(document.getElementById('extraonly'))document.getElementById('extraonly').addEventListener('change',filt);
document.getElementById('csv').addEventListener('click',()=>{
  const q=s=>'"'+String(s||'').replace(/"/g,'""')+'"';
  const rows=[['memo_id','set','company','results_differ','choice','note'].join(',')];
  document.querySelectorAll('.memo-row').forEach(r=>{const p=picks[r.dataset.memo]||{};
    rows.push([q(r.dataset.memo),q(r.dataset.set),q(r.dataset.company),r.dataset.diff,q(p.choice),q(p.note)].join(','))});
  const blob=new Blob(['\\ufeff'+rows.join('\\n')],{type:'text/csv;charset=utf-8'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='method_compare_picks.csv';a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),1000)});
"""


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


def _evidence_section(prompt: str) -> str:
    import re
    m = re.search(r"# 새 근거\n(.*?)(?=\n# |\Z)", prompt, re.S)
    return m.group(1).strip() if m else ""


def load_method(d: Path, method: str) -> dict:
    """방식 하나의 메모 분석·카드 실행 결과 (파일만)."""
    base = d / method
    runs = sorted((base / "cards").glob("run_*"))
    run = runs[-1] if runs else None
    out = {"analysis": {a["memo_id"]: a for a in _read_jsonl(base / "analysis.jsonl")}, "cards": {}, "outcomes": {},
           "responses": {}, "refs": {}, "evidence": {}, "cost_analysis": 0.0, "cost_cards": 0.0, "run": run.name if run else "",
           "gold": {g["memo_id"]: g for g in _read_jsonl(base / "gold.jsonl")}}
    out["cost_analysis"] = sum(a.get("usd") or 0 for a in out["analysis"].values())
    usage = _read_jsonl(base / "cwd/results/updates/usage_log.jsonl")
    out["cost_cards"] = sum((u.get("total") or {}).get("usd") or 0 for u in usage)
    if run is None:
        return out
    # 비용 상한으로 멈춰 빠진 메모를 다시 돌린 결과(method_compare run --memos → cards_extra)는 그 메모만 바꿔 쓴다
    extra_runs = sorted((base / "cards_extra").glob("run_*"))
    extra = set(json.loads((base / "extra_memos.json").read_text(encoding="utf-8"))) \
        if extra_runs and (base / "extra_memos.json").exists() else set()
    sources = [(run, lambda iid: iid.split(":", 1)[0] not in extra)] + ([(extra_runs[-1], lambda iid: iid.split(":", 1)[0] in extra)]
                                                                      if extra else [])
    out["runs"] = [r.name for r, _ in sources]
    out["usage_items"] = []
    for r, keep in sources:
        for c in _read_jsonl(r / "cards.jsonl"):
            if keep(c["item_id"]):
                out["cards"][c["item_id"]] = c
        out["outcomes"].update({o["item_id"]: o for o in _read_jsonl(r / "outcomes.jsonl") if keep(o["item_id"])})
        out["responses"].update({x["item_id"]: x for x in _read_jsonl(r / "responses.jsonl")
                                 if x.get("item_id") and keep(x["item_id"])})
        if (r / "refs.json").exists():
            out["refs"].update(json.loads((r / "refs.json").read_text(encoding="utf-8")))
        for row in _read_jsonl(r / "llm_io.jsonl"):
            if row.get("stage") == "card" and keep(row.get("item_id") or "") and row.get("item_id") not in out["evidence"]:
                out["evidence"][row["item_id"]] = _evidence_section(row.get("prompt") or "")
    if extra:
        usage = _read_jsonl(base / "cwd_extra/results/updates/usage_log.jsonl")
        out["cost_cards"] += sum((u.get("total") or {}).get("usd") or 0 for u in usage)
        out["run"] += " + " + extra_runs[-1].name + f" (메모 {len(extra)}개 다시)"
    return out


def _items_of(m: dict, memo_id: str) -> list[dict]:
    """gold의 항목 → [{item_id, description, kind(alert|ask), type}] (실행기 item_id 규칙과 같게)."""
    g = m["gold"].get(memo_id) or {}
    rows = []
    for s in g.get("sentences") or []:
        for i, it in enumerate(s.get("items") or []):
            if it.get("type") not in ("topic", "price_below", "price_above"):
                continue
            rows.append({"item_id": f"{memo_id}:{s['sentence_index']}:{i}", "description": it.get("description") or "",
                         "kind": "ask" if (it.get("category") == "ask" or it.get("ask")) else "alert", "type": it["type"],
                         "price": it.get("price_threshold")})
    return rows


def _hit_sentences(card: dict, codes: list[str], evidence_text: str, memo_text: str) -> list[tuple[str, list[str]]]:
    """검사에 걸린 카드의 문장마다 어떤 코드에 걸렸는지 (지금 checks 함수로 다시 본다. 형식 코드는 문장을 특정하지 않는다)."""
    import re

    from pipelines.common.config import load_config

    from .checks import (_banned_hit, evidence_number_sets, forecast_subjects, missing_subject, prediction_text,
                         strip_memo_quotes)
    from .number_check_compare import parse_evidence
    real = load_config("configs/updates.yaml")
    cfg, banned = real["topic"], list(real["banned"])
    ev = {e.eid: e for e in parse_evidence("# 새 근거\n" + evidence_text)} if evidence_text else {}
    facts = [(f.get("text") or "", f.get("evidence_id") or "") if isinstance(f, dict) else (f[0], f[1])
             for f in card.get("facts") or []]
    names = forecast_subjects(t for t, e in facts if e)
    exp = [s for s in re.split(r"(?<=[.!?])\s+", card.get("explanation") or "") if s.strip()]
    rows = [("제목", card.get("headline") or "", "")] + [("사실", t, e) for t, e in facts] + [("설명", s, "") for s in exp] \
        + [("메모 연결", card.get("memo_link") or "", "")]
    out = []
    for where, text, eid in rows:
        hit = []
        if "ATTRIBUTION" in codes and where in ("사실", "설명") and missing_subject(text):
            hit.append("ATTRIBUTION")
        if "PREDICTION" in codes and prediction_text([text], cfg, names):
            hit.append("PREDICTION")
        if "BANNED" in codes and _banned_hit([text], banned, cfg, names):
            hit.append("BANNED")
        if "COVERAGE" in codes:
            t = strip_memo_quotes(text, memo_text) if where == "메모 연결" else text
            if any(term in t for term in cfg["coverage_terms"]):
                hit.append("COVERAGE")
        if "NUMBER" in codes and where == "사실" and eid in ev:
            from .checks import _ev_text
            if not evidence_number_sets(_ev_text(ev[eid])).supports(text):
                hit.append("NUMBER")
        if text:
            out.append((f"{where}: {text}", hit))
    return out


def _vcard(c: dict, refs: dict, kind: str) -> str:
    """화면에 나갈 모양: 제목 · 본문 · 계산 · 메모와의 연결 · 출처·날짜 · 사실 문장(접기)."""
    utype = c.get("update_type") or "news"
    chip = "질문 답" if kind == "ask" else TYPE_LABEL.get(utype, utype)
    when = c.get("when") or c.get("observed_trade_date") or ""
    title = c.get("headline") or c.get("title") or ""
    facts = [f.get("text") if isinstance(f, dict) else str(f) for f in c.get("facts") or []]
    exp = c.get("explanation") or ""
    if utype == "price_condition":
        body = f"<div>{escape(c.get('summary') or '')}</div>"
        srcs = f'<div class="src">KRX · {escape(str(when))} 종가 기준</div>'
        return (f'<div class="vcard"><div class="row"><span class="chip price_condition">주가</span>'
                f'<span>{escape(str(when))}</span></div><div class="title">{escape(title)}</div>{body}'
                f'<div class="label">출처</div>{srcs}</div>')
    if exp:
        body = f"<div>{escape(exp)}</div>"
        fold = (f'<details class="fold"><summary>사실 문장 {len(facts)}개 (검증용)</summary><ul class="facts">'
                + "".join(f"<li>{escape(t)}</li>" for t in facts) + "</ul></details>") if facts else ""
    else:
        body = '<ul class="facts">' + "".join(f"<li>{escape(t)}</li>" for t in facts) + "</ul>"
        fold = ""
    calc = "".join(f'<div class="calc">🧮 {escape(k.get("label") or "")} = <b>{escape(k.get("result") or "")}</b> (코드 계산)</div>'
                   for k in c.get("calculations") or [] if k.get("ok"))
    link = f'<div class="label">내 메모와의 연결</div><div>{escape(c["memo_link"])}</div>' if c.get("memo_link") else ""
    if c.get("source_list"):
        kinds = {"disclosure": "공시", "news": "뉴스", "data": "데이터"}
        src = "".join(f'<div class="src">[{kinds.get(s.get("kind"), s.get("kind"))}] {escape(s.get("title") or "")} · '
                      f'{escape(s.get("source") or "")} {escape(s.get("date") or "")}</div>' for s in c["source_list"])
    else:
        src = "".join(_source_line(s["ref"], None, refs) for s in c.get("sources") or [])
    related = "".join(_source_line(r["ref"], None, {**refs, r["ref"]: {**refs.get(r["ref"], {}), "title": r.get("title") or ""}})
                      for r in c.get("related_news") or [])
    related = f'<div class="label">관련 기사</div>{related}' if related else ""
    cov = f'<div class="note">자료 범위: {escape(c["coverage"])}</div>' if c.get("coverage") else ""
    dev = ' <span class="dev">고정 문구</span>' if c.get("origin") == "fixed" else ""
    return (f'<div class="vcard"><div class="row"><span class="chip {escape(utype)}">{escape(chip)}</span>'
            f'<span>{escape(str(when))}</span>{dev}</div><div class="title">{escape(title)}</div>{body}{calc}{link}'
            f'<div class="label">출처</div>{src}{related}{cov}{fold}</div>')


def _no_card(m: dict, item: dict, memo_text: str) -> tuple[str, str]:
    """카드가 없을 때 그 자리의 이유 HTML과 이유 키 (요약 집계용)."""
    iid = item["item_id"]
    r = m["responses"].get(iid) or {}
    o = m["outcomes"].get(iid) or {}
    reason = r.get("reason") or o.get("kind") or "결과 없음"
    if str(reason).startswith("merged_into:"):
        return f'<div class="why">같은 근거라 {escape(reason.split(":", 1)[1])} 카드로 합쳤어요</div>', "merged"
    if r.get("type") == "ask_no_answer":
        return (f'<div class="why"><b>자료 없음 답</b> (보이는 답) · {escape(r.get("message") or "")}'
                f'<br>내부 이유: {escape(REASON_KO.get(o.get("kind") or "", o.get("kind") or reason))}</div>'), "ask_no_answer"
    checks = o.get("checks") or []
    last = next((c for c in reversed(checks) if c.get("codes")), None)   # 마지막으로 걸린 단계 (재요청 뒤 결과)
    key = reason
    if last is not None and last.get("stage") == "verify" and last is checks[-1]:
        notes = "".join(f"<li>{escape(n)}</li>" for n in last.get("notes") or [])
        return (f'<div class="why"><b>검수 실패</b> <span class="code">{escape(", ".join(last["codes"]))}</span>'
                f'<ul>{notes}</ul></div>'), "verify_failed"
    if last is not None and last is checks[-1]:
        codes = last.get("codes") or o.get("fail_codes") or []
        card = last.get("card") or {}
        hits = _hit_sentences(card, codes, m["evidence"].get(iid, ""), memo_text) if card else []
        lis = "".join(f'<li class="{"hit" if h else ""}">{escape(t)}' + (f' <span class="code">← {escape(", ".join(h))}</span>' if h else "")
                      + "</li>" for t, h in hits)
        retried = " · 형식 재요청 뒤에도" if any(c.get("stage") == "format_retry" for c in checks) else ""
        return (f'<div class="why"><b>검사 실패</b>{retried} <span class="code">{escape(", ".join(codes))}</span>'
                f'<ul>{lis}</ul></div>'), "check_failed:" + ",".join(codes)
    rel = o.get("relevance") or {}
    extra = f" · 관련성 판정 {rel.get('judged', 0)}건 중 O {rel.get('relevant', 0)}" if rel.get("judged") else ""
    return f'<div class="why">{escape(REASON_KO.get(reason, reason))}{escape(extra)}</div>', key


def _analysis_note(a: dict | None) -> str:
    if not a:
        return '<div class="anal">메모 분석 결과 없음 (실행 중단)</div>'
    parts = []
    if a.get("error"):
        parts.append(f"분석 오류: {a['error']}")
    for r in a.get("responses") or []:
        if r["type"] == "out_of_scope":
            parts.append(f"범위 밖 안내 ({r.get('scope')}): {r.get('reason') or ''}")
        elif r["type"] == "needs_confirmation":
            parts.append(f"확인 질문: {r.get('question') or ''}")
    if not a.get("items") and not a.get("asks"):
        sents = "; ".join(f"「{s['text']}」 {s['decision']}/{s.get('reason') or '-'}" for s in a.get("sentences") or [])
        parts.append(f"추적 항목·질문 없음 — 문장 판정: {sents}")
    return "".join(f'<div class="anal">{escape(p)}</div>' for p in parts)


def _ev_blocks(text: str) -> list[str]:
    import re
    blocks = re.split(r"\n(?=E\d+ \[)", text.strip()) if text.strip() else []
    return [re.sub(r"^E\d+ ", "", b).strip() for b in blocks]


EXTRA_METHODS = (("combo_c", "조합 C · 팀원 방식 + 관련성 판정 sol"),)   # method_compare derive로 만든 방식 (있으면 칸을 더한다)


def _extra_methods(d: Path) -> list[tuple[str, str]]:
    out = []
    for k, label in EXTRA_METHODS:
        if sorted((d / k / "cards").glob("run_*")):
            info = json.loads((d / k / "derived.json").read_text(encoding="utf-8")) if (d / k / "derived.json").exists() else {}
            out.append((k, label + (f" ({', '.join(info.get('set') or [])})" if info.get("set") else "")))
    return out


def build_methods(d: Path) -> str:
    methods = list(METHODS) + _extra_methods(d)
    data = {k: load_method(d, k) for k, _ in methods}
    memos = _read_jsonl(d / "dataset.jsonl")
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8")) if (d / "meta.json").exists() else {}
    freeze = json.loads((d / "freeze_check.json").read_text(encoding="utf-8")) if (d / "freeze_check.json").exists() else None
    stats = {k: {"alert": 0, "ask": 0, "price": 0, "reasons": {}, "memos": 0} for k, _ in methods}
    sub = {k: {"alert": 0, "ask": 0, "price": 0, "memo_with_card": 0} for k, _ in methods}   # 추가 방식이 돈 메모만
    extra_ids = set().union(*[set(data[k]["gold"]) for k, _ in methods[2:]]) if len(methods) > 2 else set()
    rows_html, differ = [], 0
    for memo in memos:
        mid = memo["memo_id"]
        active = [(k, label) for k, label in methods if k in ("seorin", "minyi") or mid in data[k]["gold"]]
        cols, sig = [], {}
        for k, label in active:
            m = data[k]
            stats[k]["memos"] += 1
            parts = [f'<div class="colhead">{escape(label)}</div>', _analysis_note(m["analysis"].get(mid))]
            heads = []
            for it in _items_of(m, mid):
                kind_lab = "한 번 답하기" if it["kind"] == "ask" else ("알림 · 가격" if it["type"] != "topic" else "알림")
                parts.append(f'<div class="itemlab"><span class="kind {it["kind"]}">{kind_lab}</span>{escape(it["description"])}'
                             + (f" ({it['price']:,}원)" if it.get("price") else "") + "</div>")
                c = m["cards"].get(it["item_id"])
                if c is not None:
                    parts.append(_vcard(c, m["refs"], it["kind"]))
                    heads.append(c.get("headline") or c.get("title") or "")
                    kind = "price" if (c.get("update_type") or "") == "price_condition" else it["kind"]
                    stats[k][kind] += 1
                    if mid in extra_ids:
                        sub[k][kind] += 1
                else:
                    html, key = _no_card(m, it, memo["text"])
                    parts.append(html)
                    key = key.split(":")[0] if key.startswith("check_failed") else key
                    stats[k]["reasons"][key] = stats[k]["reasons"].get(key, 0) + 1
            if mid in extra_ids and heads:
                sub[k]["memo_with_card"] += 1
            sig[k] = sorted(heads)
            cols.append("<div>" + "".join(parts) + "</div>")
        # 근거 원문: 방식마다 LLM에 넘긴 근거 블록 (모두 같으면 하나만)
        blocks = {k: [] for k, _ in active}
        for k, _ in active:
            for it in _items_of(data[k], mid):
                for b in _ev_blocks(data[k]["evidence"].get(it["item_id"], "")):
                    if b not in blocks[k]:
                        blocks[k].append(b)
        evh = ['<div class="colhead">근거 원문 (LLM이 받은 그대로)</div>']
        sets_ = [set(v) for v in blocks.values()]
        if not any(blocks.values()):
            evh.append('<div class="why">모든 방식이 카드 작성 LLM에 넘긴 근거가 없어요</div>')
        elif all(x == sets_[0] for x in sets_):
            first = next(iter(blocks.values()))
            evh.append(f'<div class="anal"><span class="same">모든 방식 같은 근거 {len(first)}건</span></div>')
            evh += [f'<details class="ev"><summary>{escape(b.splitlines()[0][:70])} · {escape(_ev_title(b))}</summary>'
                    f"<pre>{escape(b)}</pre></details>" for b in first]
        else:
            for k, label in active:
                others = set().union(*[set(v) for kk, v in blocks.items() if kk != k])
                only = [b for b in blocks[k] if b not in others]
                evh.append(f'<div class="itemlab">{escape(label)} · {len(blocks[k])}건 (이 방식에만 {len(only)}건)</div>')
                evh += [f'<details class="ev"><summary>{"★ " if b in only else ""}{escape(b.splitlines()[0][:60])} · '
                        f'{escape(_ev_title(b))}</summary><pre>{escape(b)}</pre></details>' for b in blocks[k]]
        diff = sig["seorin"] != sig["minyi"]
        differ += diff
        choices = ("서린", "팀원") + tuple(label.split(" · ")[0] for _, label in active[2:]) + ("같음", "둘 다 별로")
        pick = ('<div class="pick">' + "".join(f'<button type="button" data-v="{v}" aria-pressed="false">{v}</button>'
                                              for v in choices)
                + '<textarea placeholder="메모 (선택)" aria-label="메모"></textarea></div>')
        grid = f' style="grid-template-columns:repeat({len(active) + 1},minmax(0,1fr))"' if len(active) > 2 else ""
        extra_tag = (f'<span class="same">{escape(" · ".join(lab.split(" · ")[0] for _, lab in active[2:]))} 함께</span>'
                     if len(active) > 2 else "")
        rows_html.append(
            f'<section class="memo-row" data-memo="{escape(mid)}" data-set="{escape(memo["set"])}" '
            f'data-company="{escape(memo["company"])}" data-diff="{int(diff)}" data-extra="{int(len(active) > 2)}">'
            f'<div class="memo-head"><b>{escape(mid)} · {escape(memo["company"])}</b><span>{escape(memo["set"])}</span>'
            f'<span>{"결과 다름" if diff else "결과 같음"}</span>{extra_tag}</div>'
            f'<div class="memo-text">{escape(memo["text"])}</div>'
            f'<div class="cols"{grid}>{"".join(cols)}<div>{"".join(evh)}</div></div>{pick}</section>')
    boxes = []
    for k, label in methods:
        st, m = stats[k], data[k]
        reasons = "".join(f'<tr><td>{escape(REASON_KO.get(r, r))}</td><td class="n">{n}</td></tr>'
                          for r, n in sorted(st["reasons"].items(), key=lambda x: -x[1]))
        boxes.append(f'<div class="box"><b>{escape(label)}</b> · {escape(m["run"])} · 메모 {st["memos"]}개<table>'
                     f'<tr><td>알림 카드</td><td class="n">{st["alert"]}</td></tr>'
                     f'<tr><td>질문 답 카드</td><td class="n">{st["ask"]}</td></tr>'
                     f'<tr><td>가격 카드</td><td class="n">{st["price"]}</td></tr>'
                     f'<tr><td>비용 (메모 분석 + 카드)</td><td class="n">${m["cost_analysis"]:.2f} + ${m["cost_cards"]:.2f} = '
                     f'${m["cost_analysis"] + m["cost_cards"]:.2f}</td></tr></table>'
                     f'<div class="label">카드가 안 나온 이유</div><table>{reasons}</table></div>')
    if extra_ids:
        rows = "".join(f'<tr><td>{escape(label.split(" (")[0])}</td><td class="n">{sub[k]["alert"]}</td>'
                       f'<td class="n">{sub[k]["ask"]}</td><td class="n">{sub[k]["memo_with_card"]}</td></tr>'
                       for k, label in methods)
        boxes.append(f'<div class="box"><b>추가 방식을 돌린 메모 {len(extra_ids)}개만</b><table><tr><td></td>'
                     f'<td class="n">알림</td><td class="n">질문 답</td><td class="n">카드 있는 메모</td></tr>{rows}</table></div>')
    sets = " · ".join(f"{escape(k)} {v}" for k, v in (meta.get("sets") or {}).items())
    fz = ""
    if freeze:
        fz = (f" · 같은 DB 자료 확인: 후보 뉴스 {freeze['news_candidates']}·공시 {freeze['disclosure_candidates']}건 중 기준 시각 뒤에 "
              f"들어온 뉴스 {len(freeze['late_news'])}·공시 {len(freeze['late_disclosures'])}건, 주가 마지막 날 "
              f"{freeze['last_price_before']} → {freeze['last_price_after']}")
    extra_filter = '<label><input type="checkbox" id="extraonly"> 조합 C를 돌린 메모만</label>' if extra_ids else ""
    title = "두 방식 카드 비교 · 서린(운영) / 팀원(updates_exp)" + (" / 조합 C" if extra_ids else "")
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>두 방식 카드 비교</title><style>{CSS}{METHODS_CSS}</style></head>"
            f'<body data-run="{escape(d.name)}"><main><h1>{escape(title)}</h1>'
            f'<p class="meta">메모 {len(memos)}개 ({sets}) · 기준 시각 {escape(meta.get("as_of", ""))} · 첫 확인(조회 기간 전체) · '
            f"서린·팀원 결과가 다른 메모 {differ}개{escape(fz)}</p>"
            f'<div class="top">{"".join(boxes)}</div>'
            f'<div class="bar"><label><input type="checkbox" id="diffonly"> 두 방식 결과가 다른 메모만</label>{extra_filter}'
            f'<span>고른 메모 <b id="picked">0</b>/{len(memos)}</span><button type="button" id="csv">고른 결과 CSV 내려받기</button>'
            f'<span class="meta" style="margin:0">고른 결과는 이 브라우저에만 저장돼요</span></div>'
            f'{"".join(rows_html)}</main><script>{METHODS_JS}</script></body></html>')


def _ev_title(block: str) -> str:
    import re
    m = re.search(r"- (?:보고서명|제목): (.*)", block)
    return (m.group(1) if m else "")[:70]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="두 실행의 카드를 항목별로 나란히 보는 미리보기 (파일만 읽음)")
    ap.add_argument("run_a", nargs="?")
    ap.add_argument("run_b", nargs="?")
    ap.add_argument("--labels", default="v1,v2")
    ap.add_argument("--out")
    ap.add_argument("--methods", help="method_compare 결과 폴더: 두 방식을 메모 단위로 나란히 (서린·팀원·근거 원문)")
    args = ap.parse_args(argv)
    if args.methods:
        d = Path(args.methods)
        out = Path(args.out) if args.out else d / "method_compare.html"
        out.write_text(build_methods(d), encoding="utf-8")
        print(f"두 방식 비교: {out}")
        return 0
    a, b = load(Path(args.run_a)), load(Path(args.run_b))
    labels = tuple(args.labels.split(",", 1))
    out = Path(args.out) if args.out else Path(args.run_a).parent / f"compare_{a['name']}_{b['name']}" / "preview_compare.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(a, b, labels), encoding="utf-8")
    print(f"비교 미리보기: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
