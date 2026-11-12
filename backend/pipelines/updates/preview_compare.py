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

from .preview import CSS, EMPTY_REASON, _card_html

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="두 실행의 카드를 항목별로 나란히 보는 미리보기 (파일만 읽음)")
    ap.add_argument("run_a")
    ap.add_argument("run_b")
    ap.add_argument("--labels", default="v1,v2")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    a, b = load(Path(args.run_a)), load(Path(args.run_b))
    labels = tuple(args.labels.split(",", 1))
    out = Path(args.out) if args.out else Path(args.run_a).parent / f"compare_{a['name']}_{b['name']}" / "preview_compare.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(a, b, labels), encoding="utf-8")
    print(f"비교 미리보기: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
