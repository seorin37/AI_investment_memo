"""experiment 연속 실행 비교: 회차별 응답 유형·실패 이유·비용, 같은 근거로 다시 나온 카드, 새 자료 확인.

    PYTHONPATH=backend python -m pipelines.updates.compare_runs results/updates/run_A results/updates/run_B \
        --state-before results/updates/state_X/item_state_after_run1.json

- 같은 근거로 다시 나온 카드: 뒤 회차 update_card의 sources ref가 앞 회차 같은 항목 카드의 ref와 겹치는 수 (0이어야 한다).
- --state-before(뒤 회차를 돌리기 직전의 item_state 파일)를 주면 DB(읽기 전용)로 확인한다:
  · 뒤 회차 카드의 근거가 모두 그 항목의 마지막 확인 이후 자료인가 (검색 가능해진 시각 = 적재·임베딩 중 늦은 쪽 > 확인 시각).
  · 마지막 확인 이후 그 종목에 새 뉴스·공시가 하나도 없는 항목이 카드를 받지 않았는가.
비용은 summary.json의 토큰 × PRICES (relevance_compare). 2026-11-10 저장소 밖 compare_runs.py를 옮겼다.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from .candidates import FRESH_PUBLISHED_DAYS
from .relevance_compare import PRICES

# 마지막 확인 이후 검색 가능해진 자료 중 발행 3일 안 (experiment의 새 자료 기준과 같게, 발행 기준은 확인 시각 - 3일로 넓게 본다)
FRESH_NEWS_SQL = """SELECT count(*) FROM news_stocks ns JOIN news_articles a ON a.id = ns.news_id
LEFT JOIN news_embedding_variants v ON v.news_id = a.id AND v.variant = %(variant)s
WHERE ns.symbol = %(symbol)s AND a.published_at >= %(ts)s - make_interval(days => %(days)s)
  AND COALESCE(v.embedded_at, a.collected_at) > %(ts)s"""
FRESH_DISC_SQL = """SELECT count(*) FROM disclosure_chunks c JOIN disclosures d ON d.rcept_no = c.rcept_no
WHERE d.symbol = %(symbol)s AND d.rcept_dt >= (%(ts)s - make_interval(days => %(days)s))::date
  AND GREATEST(d.created_at, COALESCE(c.embedded_at, d.created_at)) > %(ts)s"""


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


def freshness(conn, state: dict, outcomes: list[dict], cards: dict[str, list[str]], variant: str = "hybrid") -> dict:
    """state: item_state 파일의 items (뒤 회차 직전). 뒤 회차 카드 근거가 마지막 확인 이후 검색 가능해진 자료인지,
    마지막 확인 이후 새 자료(우선주는 보통주 자료)가 없는 항목이 카드를 받았는지."""
    from .candidates import ready_times
    from .models import Candidate
    from .preferred import load_map, source_symbol

    pref_map = load_map(conn)
    symbol = {o["item_id"]: o["symbol"] for o in outcomes}
    fake = [Candidate(ref, "news" if ref.startswith("news:") else "disclosure", "", "", "", "", None, "", 0.0)
            for refs in cards.values() for ref in refs]
    published: dict = {}
    times = ready_times(conn, fake, variant, published)
    old_evidence, late_chunk = [], []
    for item_id, refs in cards.items():
        if item_id not in state:
            continue
        ts = datetime.fromisoformat(state[item_id]["last_checked_at"])
        for ref in refs:
            ready = times.get(ref)
            if ready is None or ready <= ts:
                row = {"item_id": item_id, "ref": ref, "ready": str(ready), "last_checked_at": str(ts)}
                pub = published.get(ref)
                # 확인 전부터 검색 가능했던 기사지만 발행 3일 안: 원문 청크로 찾은 late chunk 근거 (drop_not_ready가 허용)
                if pub is not None and pub >= ts - timedelta(days=FRESH_PUBLISHED_DAYS):
                    late_chunk.append({**row, "published": str(pub)})
                else:
                    old_evidence.append(row)
    no_new, carded_without_new = [], []
    with conn.cursor() as cur:
        for item_id, rec in state.items():
            if item_id not in symbol:
                continue
            p = {"symbol": source_symbol(symbol[item_id], pref_map), "ts": datetime.fromisoformat(rec["last_checked_at"]),
                 "days": FRESH_PUBLISHED_DAYS, "variant": variant}
            cur.execute(FRESH_NEWS_SQL, p)
            n_news = cur.fetchone()[0]
            cur.execute(FRESH_DISC_SQL, p)
            n_disc = cur.fetchone()[0]
            if n_news == 0 and n_disc == 0:
                no_new.append(item_id)
                if item_id in cards:
                    carded_without_new.append(item_id)
    return {"cards_checked": len(cards), "cards_with_old_evidence": old_evidence, "late_chunk_evidence": late_chunk,
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
        print(f"확인 전부터 있던 기사를 원문 청크로 찾은 근거(발행 3일 안, 허용) {len(f['late_chunk_evidence'])}개 "
              f"{f['late_chunk_evidence']}")
        print(f"마지막 확인 이후 종목에 새 뉴스·공시가 하나도 없는 항목 {f['items_without_new_material']}개 중 카드를 받은 항목: "
              f"{f['of_which_got_card']}")
    print(f"\n합계 비용 ${total:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
