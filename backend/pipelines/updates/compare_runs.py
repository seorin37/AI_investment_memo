"""experiment 연속 실행 비교: 회차별 응답 유형·실패 이유·비용, 같은 근거로 다시 나온 카드, 새 자료 확인.

    PYTHONPATH=backend python -m pipelines.updates.compare_runs results/updates/run_A results/updates/run_B \
        --state-before results/updates/state_X/item_state_after_run1.json

- 같은 근거로 다시 나온 카드: 뒤 회차 update_card의 sources ref가 앞 회차 같은 항목 카드의 ref와 겹치는 수 (0이어야 한다).
- --state-before(뒤 회차를 돌리기 직전의 item_state 파일)를 주면 DB(읽기 전용)로 확인한다:
  · 뒤 회차 카드의 근거가 모두 그 항목의 마지막 확인 이후 자료인가 (뉴스 발행 시각 > 확인 시각, 공시 접수일 >= 확인 날짜).
  · 마지막 확인 이후 그 종목에 새 뉴스·공시가 하나도 없는 항목이 카드를 받지 않았는가.
비용은 summary.json의 토큰 × PRICES (relevance_compare). 2026-11-10 저장소 밖 compare_runs.py를 옮겼다.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .relevance_compare import PRICES

FRESH_NEWS_SQL = """SELECT count(*) FROM news_stocks ns JOIN news_articles a ON a.id = ns.news_id
WHERE ns.symbol = %(symbol)s AND a.published_at > %(ts)s"""
FRESH_DISC_SQL = "SELECT count(*) FROM disclosures d WHERE d.symbol = %(symbol)s AND d.rcept_dt >= %(day)s"
NEWS_TIME_SQL = "SELECT id, published_at FROM news_articles WHERE id = ANY(%(ids)s)"
DISC_DAY_SQL = "SELECT rcept_no, rcept_dt FROM disclosures WHERE rcept_no = ANY(%(nos)s)"


def load_run(run: Path) -> tuple[dict, list[dict], list[dict]]:
    read = lambda name: [json.loads(l) for l in (run / name).read_text(encoding="utf-8").splitlines() if l.strip()]
    return json.loads((run / "summary.json").read_text(encoding="utf-8")), read("responses.jsonl"), read("outcomes.jsonl")


def cost(summary: dict) -> float | None:
    pin, pout = PRICES.get(summary.get("model"), (None, None))
    if pin is None:
        return None
    return round(summary.get("prompt_tokens", 0) * pin / 1e6 + summary.get("output_tokens", 0) * pout / 1e6, 4)


def card_refs(responses: list[dict]) -> dict[str, list[str]]:
    return {r["item_id"]: [s["ref"] for s in (r["card"] or {}).get("sources", [])]
            for r in responses if r["type"] == "update_card"}


def repeated(first: dict[str, list[str]], second: dict[str, list[str]]) -> dict[str, list[str]]:
    out = {i: sorted(set(refs) & set(first.get(i, []))) for i, refs in second.items()}
    return {i: v for i, v in out.items() if v}


def freshness(conn, state: dict, outcomes: list[dict], cards: dict[str, list[str]]) -> dict:
    """state: item_state 파일의 items (뒤 회차 직전). 뒤 회차 카드 근거의 시각과, 새 자료가 없는 항목의 카드 여부."""
    symbol = {o["item_id"]: o["symbol"] for o in outcomes}
    news_ids = sorted({int(r.split(":", 1)[1]) for refs in cards.values() for r in refs if r.startswith("news:")})
    nos = sorted({r.split(":", 1)[1].split("#", 1)[0] for refs in cards.values() for r in refs if r.startswith("disc:")})
    with conn.cursor() as cur:
        cur.execute(NEWS_TIME_SQL, {"ids": news_ids})
        news_time = {f"news:{i}": t for i, t in cur.fetchall()}
        cur.execute(DISC_DAY_SQL, {"nos": nos})
        disc_day = {n: d for n, d in cur.fetchall()}
    old_evidence = []
    for item_id, refs in cards.items():
        ts = datetime.fromisoformat(state[item_id]["last_checked_at"]) if item_id in state else None
        if ts is None:
            continue
        for ref in refs:
            when = news_time.get(ref) if ref.startswith("news:") else disc_day.get(ref.split(":", 1)[1].split("#", 1)[0])
            new = (when > ts) if ref.startswith("news:") else (when is not None and when >= ts.date())
            if not new:
                old_evidence.append({"item_id": item_id, "ref": ref, "when": str(when), "last_checked_at": str(ts)})
    no_new, carded_without_new = [], []
    with conn.cursor() as cur:
        for item_id, rec in state.items():
            if item_id not in symbol:
                continue
            ts = datetime.fromisoformat(rec["last_checked_at"])
            cur.execute(FRESH_NEWS_SQL, {"symbol": symbol[item_id], "ts": ts})
            n_news = cur.fetchone()[0]
            cur.execute(FRESH_DISC_SQL, {"symbol": symbol[item_id], "day": ts.date()})
            n_disc = cur.fetchone()[0]
            if n_news == 0 and n_disc == 0:
                no_new.append(item_id)
                if item_id in cards:
                    carded_without_new.append(item_id)
    return {"cards_checked": len(cards), "cards_with_old_evidence": old_evidence,
            "items_without_new_material": len(no_new), "of_which_got_card": carded_without_new}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="experiment 연속 실행 비교 (DB 읽기 전용)")
    ap.add_argument("runs", nargs="+", help="실행 폴더 (순서대로)")
    ap.add_argument("--state-before", help="마지막 회차 직전의 item_state 파일 (새 자료 확인)")
    args = ap.parse_args(argv)
    runs = [Path(p) for p in args.runs]
    total, cards = 0.0, []
    for n, run in enumerate(runs, 1):
        s, resp, _ = load_run(run)
        r, usd = s["responses"], cost(s)
        total += usd or 0
        print(f"== {n}회차 {run.name} · 모델 {s.get('model')} · 호출 {s.get('llm_calls')} · 입력 {s.get('prompt_tokens')} · "
              f"출력 {s.get('output_tokens')} (추론 {s.get('reasoning_tokens')}) · 비용 ${usd}")
        print("  유형:", {k: r["by_type"][k] for k in ("update_card", "no_new_info", "price_card", "no_data", "needs_confirmation")},
              "· 사용자 표시", r["user_visible"])
        print("  이유별:", json.dumps(r["reasons"], ensure_ascii=False))
        print("  처리 결과:", s["outcomes"], "· 검사 실패 코드:", s.get("llm_check_failures"),
              "· 새 자료만 받은 항목:", s.get("fresh_items"), "· 쓴 근거라 뺀 후보:", (s.get("used_refs") or {}).get("skipped"))
        cards.append(card_refs(resp))
    if len(cards) >= 2:
        again = repeated(cards[-2], cards[-1])
        print(f"\n마지막 회차 카드 {len(cards[-1])}건 중 직전 회차와 같은 근거를 다시 쓴 카드: {len(again)}건 {again}")
        print(f"직전 회차 카드 항목 중 마지막 회차에도 카드가 나온 항목: {sorted(set(cards[-2]) & set(cards[-1]))}")
    if args.state_before:
        import psycopg

        from ..common.db import get_read_dsn

        state = json.loads(Path(args.state_before).read_text(encoding="utf-8"))["items"]
        _, _, outcomes = load_run(runs[-1])
        with psycopg.connect(get_read_dsn()) as conn:
            conn.read_only = True
            f = freshness(conn, state, outcomes, cards[-1])
            conn.rollback()
        print(f"\n새 자료 확인: 마지막 회차 카드 {f['cards_checked']}건 중 마지막 확인 이전 근거를 쓴 카드 근거 "
              f"{len(f['cards_with_old_evidence'])}개 {f['cards_with_old_evidence']}")
        print(f"마지막 확인 이후 종목에 새 뉴스·공시가 하나도 없는 항목 {f['items_without_new_material']}개 중 카드를 받은 항목: "
              f"{f['of_which_got_card']}")
    print(f"\n합계 비용 ${total:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
