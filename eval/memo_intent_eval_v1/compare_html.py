"""두 실행(run_service 결과 폴더)을 메모별로 나란히 보여 주는 HTML (2026-11-17).

    python eval/memo_intent_eval_v1/compare_html.py --cases <cases.jsonl> --a <기존 run 폴더> --b <개선 run 폴더> --out <html>
"""

from __future__ import annotations

import argparse
import csv
import glob
import html
import json
from pathlib import Path

KIND_KO = {"definition": "뜻 질문", "causal": "사실·숫자 확인", "comparison": "비교", "tracking": "알림 요청",
           "price_condition": "가격 조건", "non_tracking": "추적 안 함", "clarification": "확인 질문"}
REASON_KO = {"llm_no_update": "새 소식·답 없음", "no_relevant_candidates": "관련 근거 0건", "no_candidates": "후보 없음",
             "price_unchanged": "가격 조건 변화 없음", "check_failed": "코드 검사 실패", "verify_failed": "검수 실패",
             "no_source_data": "자료 없음", "call_failed": "호출 실패", "relevance_failed": "판정 실패"}


def load_run(run: Path) -> dict:
    cdir = Path(sorted(glob.glob(str(run / "cards" / "run_*")))[-1])
    read = lambda p: [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    usd = sum(float(r["usd"] or 0) for r in csv.DictReader((cdir / "usage_by_item.csv").open(encoding="utf-8-sig")))
    return {"analysis": {a["memo_id"]: a for a in read(run / "analysis.jsonl")},
            "gold": {g["memo_id"]: g for g in read(run / "gold_from_analysis.jsonl")},
            "cards": {c["item_id"]: c for c in read(cdir / "cards.jsonl")},
            "resp": {r["item_id"]: r for r in read(cdir / "responses.jsonl") if r.get("item_id")},
            "score": json.loads((run / "score.json").read_text(encoding="utf-8")), "usd": usd}


def esc(s) -> str:
    return html.escape(str(s or ""))


def card_html(c: dict) -> str:
    facts = "".join(f"<li>{esc(f.get('text') if isinstance(f, dict) else f)}</li>" for f in c.get("facts") or [])
    calc = "".join(f"<div class='calc'>🧮 {esc(k['label'])} = <b>{esc(k['result'])}</b> <span class='muted'>(코드 계산)</span></div>"
                   for k in c.get("calculations") or [] if k.get("ok"))
    exp = f"<div class='exp'>{esc(c['explanation'])}</div>" if c.get("explanation") else ""
    if c.get("source_list"):    # 2026-11-18 종합 답변: 답 본문 + 출처 목록, facts는 검증용이라 접어 둔다
        src = "".join(f"<li>[{esc({'news': '뉴스', 'disclosure': '공시', 'data': '데이터'}.get(s.get('kind'), s.get('kind')))}] "
                      f"{esc(s.get('title'))} <span class='muted'>({esc(s.get('source'))} {esc(s.get('date'))})</span></li>"
                      for s in c["source_list"])
        return (f"<div class='card'><div class='hl'>💬 {esc(c.get('headline') or c.get('title'))}</div>"
                f"<div class='ans'>{esc(c.get('explanation'))}</div>{calc}<div class='muted'>출처</div><ul class='src'>{src}</ul>"
                f"<details><summary class='muted'>검증용 사실 {len(c.get('facts') or [])}개</summary><ul>{facts}</ul></details></div>")
    return (f"<div class='card'><div class='hl'>{esc(c.get('headline') or c.get('title'))}"
            f" <span class='muted'>{esc(c.get('when'))}</span></div><ul>{facts}</ul>{calc}{exp}"
            f"<div class='link'>↳ {esc(c.get('memo_link') or c.get('reason'))}</div></div>")


def side(run: dict, mid: str) -> tuple[str, dict]:
    """한 실행의 메모 결과 HTML과 요약 {answered, asks, items}."""
    a, g = run["analysis"][mid], run["gold"].get(mid, {"sentences": []})
    out, answered = [], 0
    for s in g["sentences"]:
        for i, it in enumerate(s["items"]):
            iid = f"{mid}:{s['sentence_index']}:{i}"
            tag = "💬 한 번 답하기" if it.get("ask") else ("💲 가격 조건" if str(it.get("type", "")).startswith("price") else "🔔 추적 항목")
            out.append(f"<div class='item'><span class='tag'>{tag}</span> {esc(it['description'])}</div>")
            c, r = run["cards"].get(iid), run["resp"].get(iid, {})
            if c:
                answered += 1
                out.append(card_html(c))
            elif r.get("type") == "ask_no_answer":
                out.append(f"<div class='none ask'>💬 자료 없음 답: {esc(r.get('message'))}"
                           f" <span class='muted'>({esc(REASON_KO.get(r.get('reason'), r.get('reason')))})</span></div>")
            else:
                out.append(f"<div class='none'>카드 없음 — {esc(REASON_KO.get(r.get('reason'), r.get('reason') or '-'))}"
                           " <span class='muted'>(사용자에게 안 보임)</span></div>")
    if not g["sentences"]:
        out.append("<div class='none'>추적 항목·질문 없음</div>")
    sc = a["score"]
    marks = " ".join(f"<span class='{'ok' if r['ok'] else 'bad'}'>{'✓' if r['ok'] else '✗'} {esc(KIND_KO.get(r['kind'], r['kind']))}</span>"
                     for r in sc["intents"])
    return f"<div class='score'>메모 이해: {marks}</div>" + "".join(out), {"answered": answered, "ok": sc["memo_ok"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label-a", default="기존 코드")
    ap.add_argument("--label-b", default="개선 코드")
    args = ap.parse_args()
    cases = [json.loads(l) for l in Path(args.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
    A, B = load_run(Path(args.a)), load_run(Path(args.b))
    rows = []
    for c in cases:
        mid = c["memo_id"]
        ha, sa = side(A, mid)
        hb, sb = side(B, mid)
        kinds = {e["kind"] for e in c["expected_intents"]}
        has_q = bool(kinds & {"definition", "causal", "comparison"})
        diff = sa["answered"] != sb["answered"] or sa["ok"] != sb["ok"]
        intents = "".join(f"<li><span class='tag'>{esc(KIND_KO.get(e['kind'], e['kind']))}</span> {esc(e['text'])}"
                          f"{' → 추적 필요' if e.get('create_tracking') else ''}</li>" for e in c["expected_intents"])
        rows.append(f"<section class='memo' data-q='{int(has_q)}' data-diff='{int(diff)}'>"
                    f"<h3>{esc(mid)} · {esc(c['company'])}</h3><pre>{esc(c['text'])}</pre>"
                    f"<div class='muted'>기대 의도</div><ul class='intents'>{intents}</ul>"
                    f"<div class='cols'><div class='col'><h4>{esc(args.label_a)}</h4>{ha}</div>"
                    f"<div class='col'><h4>{esc(args.label_b)}</h4>{hb}</div></div></section>")
    sa, sb = A["score"], B["score"]
    summary = (f"<table class='sum'><tr><th></th><th>{esc(args.label_a)}</th><th>{esc(args.label_b)}</th></tr>"
               f"<tr><td>메모 이해 (메모 전부 맞음)</td><td>{sa['memo_ok']}/{sa['memos']}</td><td>{sb['memo_ok']}/{sb['memos']}</td></tr>"
               f"<tr><td>메모 이해 (의도)</td><td>{sa['intents_ok']}/{sa['intents']}</td><td>{sb['intents_ok']}/{sb['intents']}</td></tr>"
               f"<tr><td>카드(답) 수</td><td>{len(A['cards'])}</td><td>{len(B['cards'])}</td></tr>"
               f"<tr><td>답 생성 비용</td><td>${A['usd']:.2f}</td><td>${B['usd']:.2f}</td></tr></table>")
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>메모 답변 비교</title><style>
:root{{--bg:#fafaf8;--fg:#1f2328;--muted:#6b7280;--line:#e5e7eb;--card:#fff;--ok:#15803d;--bad:#b91c1c;--accent:#2563eb;--ask:#7c3aed}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#e6e6e6;--muted:#9aa0a6;--line:#2c2f36;--card:#1e2127;--ok:#4ade80;--bad:#f87171;--accent:#60a5fa;--ask:#a78bfa}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.6 system-ui,'Malgun Gothic',sans-serif;margin:0;padding:16px}}
.wrap{{max-width:1200px;margin:auto}} h1{{font-size:20px}} pre{{white-space:pre-wrap;background:var(--card);border:1px solid var(--line);padding:8px;border-radius:6px}}
.sum{{border-collapse:collapse;margin:8px 0 16px}} .sum td,.sum th{{border:1px solid var(--line);padding:4px 10px;text-align:left}}
.bar label{{margin-right:14px}} .memo{{border-top:2px solid var(--line);padding:12px 0}} h3{{margin:4px 0}} h4{{margin:6px 0;color:var(--accent)}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:12px}} @media(max-width:760px){{.cols{{grid-template-columns:1fr}}}}
.col{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;min-width:0}}
.card{{border-left:3px solid var(--accent);padding:4px 8px;margin:4px 0 10px}} .hl{{font-weight:600}} .card ul{{margin:4px 0;padding-left:18px}}
.exp{{color:var(--muted);font-size:13px}} .link{{font-size:13px}} .calc{{font-size:13px}} .none{{color:var(--muted);margin:2px 0 8px}} .none.ask{{color:var(--ask)}}
.tag{{display:inline-block;font-size:12px;border:1px solid var(--line);border-radius:10px;padding:0 6px;margin-right:4px}}
.item{{margin-top:6px}} .muted{{color:var(--muted);font-size:12px}} .ok{{color:var(--ok)}} .bad{{color:var(--bad)}} .score{{font-size:13px;margin-bottom:4px}}
.intents{{margin:2px 0 8px;padding-left:18px}} .ans{{margin:4px 0 6px}} .src{{margin:2px 0;padding-left:18px;font-size:12.5px}}
</style></head><body><div class="wrap"><h1>메모 답변 비교 — {esc(args.label_a)} vs {esc(args.label_b)}</h1>
{summary}<div class="bar"><label><input type="checkbox" id="q"> 질문이 있는 메모만</label><label><input type="checkbox" id="d"> 결과가 다른 메모만</label>
<span id="cnt" class="muted"></span></div>{''.join(rows)}</div>
<script>
const q=document.getElementById('q'),d=document.getElementById('d'),cnt=document.getElementById('cnt');
function f(){{let n=0;document.querySelectorAll('.memo').forEach(m=>{{const s=(!q.checked||m.dataset.q==='1')&&(!d.checked||m.dataset.diff==='1');m.style.display=s?'':'none';n+=s}});cnt.textContent=n+'개 표시';}}
q.onchange=f;d.onchange=f;f();
</script></body></html>"""
    Path(args.out).write_text(page, encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
