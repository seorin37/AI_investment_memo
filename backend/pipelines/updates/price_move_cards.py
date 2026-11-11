"""확인용 (2026-11-11): '주가 등락률만 있고 원인이 없는 기사'로 만든 카드를 센다. 파일만 읽는다 (DB·LLM 없음), 아무것도 고치지 않는다.

    PYTHONPATH=backend python -m pipelines.updates.price_move_cards [실행 폴더 ...]   # 기본: results/updates/run_* 중 LLM 카드가 있는 것

판정 (규칙으로 후보를 뽑고 사람이 목록을 읽고 확정하는 용도. 원인 표현 규칙은 "美기술주 급락에 ~↓"처럼 '~에'로 원인을 말한
제목을 놓치고, "외국인 매도"처럼 시장 전체 원인만 있는 기사도 '원인 있음'으로 볼 수 있어 숫자는 참고만):
1) 주가 등락 카드: 카드 제목·문장에 주가 낱말(주가·종가·마감·장중·시총)과 % 숫자가 함께 있다.
2) 근거 기사에 원인이 없다: 카드가 쓴 뉴스 근거(candidates.csv의 내용 = LLM이 본 글)에 원인 표현
   (때문·영향·여파·덕분·힘입·기대감·우려·실망·발표·소식·이유·배경·호조·부진·수급·매수세·매도세 등)이 하나도 없다.
   근거가 여럿이면 하나라도 원인 표현이 있으면 '원인 있음'으로 본다. 공시 근거만 쓴 카드는 세지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

# 주가 낱말만 (D램 가격 같은 제품 가격 카드는 세지 않는다)
PRICE_WORDS = re.compile(r"주가|종가|마감|장중|시가총액|시총|거래를\s*마쳤")
PCT = re.compile(r"\d+(?:\.\d+)?\s*%")
CAUSE = re.compile(r"때문|영향|여파|덕분|힘입|기대감|기대가|우려|실망|발표|소식|이유|배경|호조|부진|수급|매수세|매도세|"
                   r"순매수|순매도|차익\s*실현|이후|따라|겹치|반영|전망|가능성|계약|수주|실적")


def card_text(c: dict) -> str:
    facts = " ".join(f.get("text", "") for f in c.get("facts") or [])
    return f"{c.get('title', '')} {c.get('summary', '')} {facts}"


def is_price_move(c: dict) -> bool:
    t = card_text(c)
    return bool(PRICE_WORDS.search(t) and PCT.search(t))


def has_cause(text: str) -> bool:
    return bool(CAUSE.search(text or ""))


def scan(run: Path) -> list[dict]:
    cards_path = run / "cards.jsonl"
    if not cards_path.exists():
        return []
    cards = [json.loads(l) for l in cards_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    cards = [c for c in cards if c.get("origin") == "llm" and c.get("update_type") != "price_condition"]
    if not cards:
        return []
    text = {}
    cpath = run / "candidates.csv"
    if cpath.exists():
        with cpath.open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                text.setdefault((r["item_id"], r["ref"]), f"{r['제목']} {r['내용(앞부분)']}")
    out = []
    for c in cards:
        news = [s["ref"] for s in c.get("sources", []) if s["ref"].startswith("news:")]
        if not news or not is_price_move(c):
            continue
        seen = [text.get((c["item_id"], ref), "") for ref in news]
        out.append({"run": run.name, "item_id": c["item_id"], "title": c.get("headline") or c.get("title"),
                    "card_has_cause": has_cause(card_text(c)), "article_has_cause": any(has_cause(t) for t in seen),
                    "refs": news, "article": [t[:160] for t in seen]})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="주가 등락률만 있고 원인이 없는 기사로 만든 카드 세기 (파일만 읽음)")
    ap.add_argument("runs", nargs="*")
    args = ap.parse_args(argv)
    from ..common.config import REPO_ROOT

    runs = [Path(r) for r in args.runs] or sorted((REPO_ROOT / "results/updates").glob("run_*"))
    total_cards, rows = 0, []
    for run in runs:
        cards_path = run / "cards.jsonl"
        if cards_path.exists():
            total_cards += sum(1 for l in cards_path.read_text(encoding="utf-8").splitlines()
                               if l.strip() and json.loads(l).get("origin") == "llm"
                               and json.loads(l).get("update_type") != "price_condition")
        rows += scan(run)
    no_cause = [r for r in rows if not r["article_has_cause"]]
    print(f"실행 {len(runs)}개 · LLM 카드 {total_cards}건 · 그중 주가 등락 카드(뉴스 근거) {len(rows)}건 · "
          f"근거 기사에 원인 표현이 없는 카드 {len(no_cause)}건")
    for r in rows:
        mark = "원인 없음" if not r["article_has_cause"] else "원인 있음"
        print(f"- [{mark}] {r['run']} {r['item_id']} {r['title']} · 카드 문장에 원인 {'있음' if r['card_has_cause'] else '없음'} · {r['refs']}")
        for t in r["article"]:
            print(f"    근거: {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
