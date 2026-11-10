"""no_data 검증 (LLM 없음, DB 읽기 전용). 결과는 화면 출력만.

    PYTHONPATH=backend python -m pipelines.updates.nodata_check --until 2026-11-09

- (b) 조회 기간 전체(recent.lookback_days, 기본 365일)에 뉴스·공시가 하나도 없는 KOSPI 종목 수를 센다 (2026-11-10 기준).
  비교용으로 최근 구간(--recent-since ~ until)에만 없는 종목 수도 센다 (이제는 no_new_info).
  앞에서 --n개로 주제 항목을 만들어 응답 유형이 no_data(no_source_data)인지, 최근에만 없는 종목은 no_new_info인지 본다.
- (a) 종가가 하나도 없는 종목, 마지막 종가가 시장 최근 거래일보다 3거래일 넘게 오래된 종목(stale_price)으로 가격 항목을 만들어 본다.
2026-11-10 저장소 밖 nodata_check.py를 옮겼다.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..common.config import load_config
from .models import TrackingItem

NO_SOURCE_SQL = """SELECT btrim(s.symbol), s.name FROM stocks s
WHERE s.market::text = 'KOSPI'
  AND NOT EXISTS (SELECT 1 FROM news_stocks ns JOIN news_articles a ON a.id = ns.news_id
                  WHERE ns.symbol = s.symbol AND a.published_at >= %(since)s AND a.published_at < %(until)s)
  AND NOT EXISTS (SELECT 1 FROM disclosures d WHERE d.symbol = s.symbol AND d.rcept_dt >= %(since_d)s AND d.rcept_dt <= %(until_d)s)
ORDER BY s.symbol"""
NO_PRICE_SQL = """SELECT btrim(s.symbol), s.name FROM stocks s
WHERE NOT EXISTS (SELECT 1 FROM prices_daily p WHERE p.symbol = s.symbol) ORDER BY s.symbol"""
LAST_PRICE_SQL = """SELECT btrim(s.symbol), s.name, max(p.trade_date) FROM stocks s JOIN prices_daily p ON p.symbol = s.symbol
WHERE s.market::text = 'KOSPI' GROUP BY 1, 2"""


def no_source(conn, since: date, until: date) -> list[tuple[str, str]]:
    kst = ZoneInfo("Asia/Seoul")
    with conn.cursor() as cur:
        cur.execute(NO_SOURCE_SQL, {"since": datetime.combine(since, datetime.min.time(), kst),
                                    "until": datetime.combine(until + timedelta(days=1), datetime.min.time(), kst),
                                    "since_d": since, "until_d": until})
        return cur.fetchall()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="no_data 검증 (LLM 없음, DB 읽기 전용)")
    ap.add_argument("--until", default="2026-11-09")
    ap.add_argument("--recent-since", default="2026-11-01", help="비교용 최근 구간 시작 (이 구간에만 없으면 no_new_info)")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--config", default="configs/updates.yaml")
    args = ap.parse_args(argv)

    import psycopg

    from ..common.db import get_read_dsn
    from .experiment import PRICE_SQL
    from .price import STALE_TRADING_DAYS, market_dates, price_outcome, trading_lag
    from .response import item_response, lookback_since, source_data
    from .topic import check_topic

    cfg = load_config(args.config)
    until = date.fromisoformat(args.until)
    since = lookback_since(cfg, until)
    recent = date.fromisoformat(args.recent_since)
    rows = []
    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        total = conn.execute("SELECT count(*) FROM stocks WHERE market::text = 'KOSPI'").fetchone()[0]
        from .preferred import load_map, source_symbol
        pref_map = load_map(conn)
        own_year = no_source(conn, since, until)                 # 종목 자기 코드로 셌을 때
        own_recent = no_source(conn, recent, until)
        # 우선주는 보통주의 공시·뉴스로 본다 (2026-11-10): 보통주에 자료가 있으면 no_data가 아니다
        mapped = lambda rows: [x for x in rows if source_symbol(x[0], pref_map) == x[0]
                               or source_symbol(x[0], pref_map) in {r[0] for r in rows}]
        none_year, none_recent = mapped(own_year), mapped(own_recent)
        print(f"(우선주→보통주 매핑 전: 기간 전체 없음 {len(own_year)}개, 최근 없음 {len(own_recent)}개 · 매핑 {len(pref_map)}개)")
        print(f"KOSPI {total}개 중")
        print(f"- 조회 기간 전체({since}~{until})에 뉴스·공시가 하나도 없는 종목 (no_data): {len(none_year)}개 {none_year[:20]}")
        import re
        pref = [x for x in none_year if re.search(r"\d?우[A-Z]?(\(전환\))?$", x[1])]
        print(f"  · 그중 우선주(이름이 '우'·'2우B'·'우(전환)'로 끝남): {len(pref)}개, 그 밖: {len(none_year) - len(pref)}개 "
              f"{[x for x in none_year if x not in pref][:20]}")
        print(f"- 최근({recent}~{until})에만 없는 종목 (no_new_info): {len(none_recent) - len(none_year)}개"
              f" (최근 구간에 없는 종목 전체 {len(none_recent)}개)")
        dates = market_dates(conn)
        stale = [(s, n, d, trading_lag(d, dates)) for s, n, d in conn.execute(LAST_PRICE_SQL).fetchall()
                 if trading_lag(d, dates) > STALE_TRADING_DAYS]
        no_price = conn.execute(NO_PRICE_SQL).fetchall()
        print(f"- 종가가 하나도 없는 종목: {len(no_price)}개 · 마지막 종가가 시장 최근 거래일({dates[0] if dates else None})보다 "
              f"{STALE_TRADING_DAYS}거래일 넘게 오래된 KOSPI 종목: {len(stale)}개 {stale[:10]}")

        recent_only = [x for x in none_recent if x not in set(none_year)]
        pref_rescued = [x for x in own_year if x not in none_year][:args.n]     # 매핑으로 no_data에서 빠진 우선주
        for label, picks in (("기간 전체 없음", none_year[:args.n]), ("최근만 없음", recent_only[:args.n]),
                             ("우선주(보통주 자료)", pref_rescued)):
            for sym, name in picks:
                item = TrackingItem(f"NODATA:{sym}:0", sym, "topic", f"{name} 실적 발표", ("실적",), company_name=name)
                data = source_data(conn, source_symbol(sym, pref_map), since, until)
                out = check_topic(item, [], None, [], {"on_check_fail": "drop"})   # 후보가 없다고 두고 LLM 없이
                r = item_response(item, out.kind, out.fail_codes, None, any(data.values()), "NODATA")
                rows.append((label, sym, name, "topic", data, r.type, r.reason, r.user_visible))
        for label, picks in (("종가 없음", [(s, n) for s, n in no_price[:args.n]]),
                             ("오래된 종가", [(s, n) for s, n, *_ in stale[:args.n]])):
            for sym, name in picks:
                item = TrackingItem(f"NODATA:{sym}:1", sym, "price_below", "10,000원 아래로", price_threshold=10000)
                prices = conn.execute(PRICE_SQL, {"symbol": sym}).fetchall()
                kind, _, info = price_outcome(item, prices, dates, cfg["price"]["near_pct"])
                r = item_response(item, kind, [], None, None, "NODATA")
                rows.append((label, sym, name, "price", info, r.type, r.reason, r.user_visible))
        conn.rollback()
    print("\n구분 | 종목 | 이름 | 항목 | 자료 | 응답 유형 | reason | 사용자 표시")
    for r in rows:
        print(" | ".join(str(x) for x in r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
