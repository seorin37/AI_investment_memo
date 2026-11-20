"""실험 실행 폴더 → 카드 검토 페이지 review.html (파일만 읽음, DB·LLM 없음) (2026-11-13).

    PYTHONPATH=backend python -m pipelines.updates.card_review_page results/updates/<...>/run_<시각>

화면에 나갈 카드 모양(헤드라인 · 설명 문단 · 메모와의 연결 · 출처·날짜·자료 범위)과 LLM이 받은 근거 원문을 나란히 놓아
"근거에 없는 말이 들어갔는지", "원하는 문체인지"를 사람이 확인한다. 카드가 없는 항목은 이유만 아래에 모은다.
근거 원문은 llm_io.jsonl(experiment --save-llm-io)의 카드 프롬프트에서 "# 새 근거" 부분을 잘라 보여 준다.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from html import escape
from pathlib import Path

CSS = """
:root{--bg:#f4f5f7;--fg:#1d1d1f;--muted:#6b6b70;--line:#e1e2e6;--card:#fff;--acc:#2456c9;--soft:#eef2fb}
@media (prefers-color-scheme: dark){:root{--bg:#141416;--fg:#ececef;--muted:#9a9aa2;--line:#2c2c31;--card:#1d1d21;--acc:#8fb0ff;--soft:#1f2533}}
body{background:var(--bg);color:var(--fg);font:15px/1.7 -apple-system,"Segoe UI","Malgun Gothic",sans-serif;margin:0;padding:24px 16px}
main{max-width:1100px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}.muted{color:var(--muted);font-size:13px}
.row{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:16px;margin:22px 0;padding-top:18px;border-top:1px solid var(--line)}
@media (max-width:820px){.row{grid-template-columns:1fr}}
.memo{background:var(--soft);border-radius:10px;padding:10px 12px;white-space:pre-wrap;font-size:14px;margin-bottom:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.h{font-size:17px;font-weight:700;margin-bottom:6px}.link{margin-top:10px;padding-top:10px;border-top:1px dashed var(--line)}
.foot{margin-top:10px;color:var(--muted);font-size:12.5px}pre{white-space:pre-wrap;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:10px 12px;font-size:13px;max-height:460px;overflow:auto;margin:0}details{margin-top:8px}summary{cursor:pointer;color:var(--muted);font-size:13px}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left;vertical-align:top}
a{color:var(--acc)}ol{margin:4px 0 0 18px;padding:0}
"""


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.is_file() else []


def _evidence_text(prompt: str) -> str:
    """카드 프롬프트에서 "# 새 근거" ~ 다음 "# " 제목 전까지."""
    m = re.search(r"# 새 근거\n(.*?)(?=\n# )", prompt, re.S)
    return m.group(1).strip() if m else ""


def _card(c: dict, refs: dict) -> str:
    src = []
    for f in c.get("facts") or []:
        r = refs.get(f.get("ref") or "")
        if r and not any(s[0] == f["ref"] for s in src):
            src.append((f["ref"], r))
    foot = " · ".join(
        (f"<a href='{escape(r['url'])}' target='_blank' rel='noopener'>{escape(r.get('source') or '')}</a>" if r.get("url")
         else escape(r.get("source") or "공시")) + f" {escape(str(r.get('date') or ''))}" for _, r in src)
    if c.get("coverage"):
        foot += f" · {escape(c['coverage'])}"
    facts = "".join(f"<li>{escape(f['text'])}</li>" for f in c.get("facts") or [])
    body = (f"<p style='margin:0'>{escape(c['explanation'])}</p>" if c.get("explanation")
            else f"<p style='margin:0'>{escape(c.get('summary') or '')}</p>")
    return (f"<div class='card'><div class='h'>{escape(c.get('headline') or c.get('title') or '')}</div>{body}"
            f"<div class='link'><b>메모와의 연결</b> {escape(c.get('memo_link') or c.get('reason') or '')}</div>"
            f"<div class='foot'>{foot} · 사건 날짜 {escape(c.get('when') or '')}</div>"
            f"<details><summary>사실 문장 {len(c.get('facts') or [])}개 (근거 대조용)</summary><ol>{facts}</ol></details></div>")


def build(run: Path) -> str:
    cards = _jsonl(run / "cards.jsonl")
    refs = json.loads((run / "refs.json").read_text(encoding="utf-8")) if (run / "refs.json").is_file() else {}
    resp = {r["item_id"]: r for r in _jsonl(run / "responses.jsonl")}
    prompts: dict[str, str] = {}
    for c in _jsonl(run / "llm_io.jsonl"):
        if c["stage"] == "card" and c["item_id"] not in prompts:
            prompts[c["item_id"]] = c["prompt"]
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8")) if (run / "summary.json").is_file() else {}
    kinds = Counter(r["type"] for r in resp.values())
    parts = [f"<h1>카드 검토</h1><div class='muted'>{escape(run.name)} · 항목 {len(resp)}개 · 응답 {dict(kinds)} · 카드 {len(cards)}장"
             f" · 모델 {escape(str(summary.get('model')))}</div>"
             "<div class='muted'>왼쪽: 화면에 나갈 카드 모양 · 오른쪽: LLM이 받은 근거 원문. 근거에 없는 숫자·사실이 있는지, 원하는 문체인지 확인하세요.</div>"]
    for c in cards:
        if c.get("item_type") not in (None, "topic"):
            continue
        ev = _evidence_text(prompts.get(c["item_id"], ""))
        parts.append(f"<div class='row'><div><div class='muted'>항목 {escape(c['item_id'])} · {escape(c.get('symbol') or '')}"
                     f" · {escape(c.get('description') or '')}</div><div class='memo'>{escape(c.get('memo_text') or '')}</div>"
                     f"{_card(c, refs)}</div><div><div class='muted'>LLM이 받은 근거</div><pre>{escape(ev) or '(근거 원문 없음)'}</pre></div></div>")
    rest = [r for iid, r in resp.items() if r["type"] not in ("update_card", "price_card")]
    rows = "".join(f"<tr><td>{escape(r['item_id'])}</td><td>{escape(r['type'])}</td><td>{escape(r.get('reason') or '')}"
                   f" {escape(' '.join(r.get('fail_codes') or []))}</td></tr>" for r in rest)
    parts.append(f"<h2 style='margin-top:36px'>카드가 없는 항목 {len(rest)}개</h2>"
                 f"<table><tr><th>항목</th><th>응답</th><th>이유</th></tr>{rows}</table>")
    return ("<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>카드 검토</title><style>{CSS}</style></head><body><main>{''.join(parts)}</main></body></html>")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="실험 실행 폴더 → 카드 검토 페이지 review.html")
    ap.add_argument("run")
    args = ap.parse_args(argv)
    run = Path(args.run)
    out = run / "review.html"
    out.write_text(build(run), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
