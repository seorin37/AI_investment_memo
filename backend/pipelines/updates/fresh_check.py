"""새 자료만 받기(FRESH_DISCLOSURE) 점검: 기준 날짜 이후 접수한 정정 공시가 새 자료로 들어가는지 빠지는지 본다 (DB 읽기 전용).

    PYTHONPATH=backend python -m pipelines.updates.fresh_check --since 2026-08-01 --symbols 005930,000660,035420,105560

기준 날짜 이후 접수한 공시 중 제목에 '정정'이 있는 것을 보여 주고, FRESH_DISCLOSURE를 통과하는지(새 자료),
빠지는지(원본이 기준 날짜 0시 전에 적재돼 있었음)와 찾은 원본을 함께 적는다. 결과는 화면 출력만.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .candidates import BASE_TITLE, CORRECTION_DAYS, EVENT_KINDS, FRESH_DISCLOSURE

SQL = f"""SELECT btrim(d.symbol), d.rcept_no, d.rcept_dt, d.kind::text, d.period_end, d.title,
       ({FRESH_DISCLOSURE}) AS fresh,
       (SELECT string_agg(d0.rcept_no || ' ' || d0.rcept_dt || ' ' || d0.title, ' / ' ORDER BY d0.rcept_dt)
          FROM disclosures d0
         WHERE d0.symbol = d.symbol AND d0.kind = d.kind AND d0.rcept_no <> d.rcept_no AND d0.rcept_dt <= d.rcept_dt
           AND {BASE_TITLE.format(t="d0")} = {BASE_TITLE.format(t="d")}
           AND CASE WHEN d.kind::text IN {EVENT_KINDS} THEN d0.rcept_dt >= d.rcept_dt - {CORRECTION_DAYS}
                    ELSE d0.period_end IS NOT DISTINCT FROM d.period_end END) AS originals
FROM disclosures d
WHERE d.symbol = ANY(%(symbols)s) AND d.rcept_dt >= %(pub_since)s AND d.title ~ '정정'
ORDER BY d.symbol, d.rcept_dt"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="새 자료만 받기: 정정 공시 처리 점검 (DB 읽기 전용)")
    ap.add_argument("--since", required=True, help="기준 날짜 (마지막 확인 날짜라고 가정)")
    ap.add_argument("--symbols", default="005930,000660,035420,105560")
    args = ap.parse_args(argv)

    import psycopg

    from ..common.db import get_read_dsn

    with psycopg.connect(get_read_dsn()) as conn:
        conn.read_only = True
        day = date.fromisoformat(args.since)
        ts = datetime.combine(day, datetime.min.time(), ZoneInfo("Asia/Seoul"))   # 그날 0시에 확인했다고 본다
        rows = conn.execute(SQL, {"symbols": args.symbols.split(","), "pub_since": day, "fresh_ts": ts}).fetchall()
        conn.rollback()
    print(f"{args.since} 이후 접수한 정정 공시 {len(rows)}건 (새 자료 {sum(r[6] for r in rows)}건, 뺌 {sum(not r[6] for r in rows)}건)")
    for sym, no, day, kind, pend, title, fresh, originals in rows:
        print(f"- {'새 자료' if fresh else '뺌    '} {sym} {no} {day} [{kind}] {title} (기간 끝 {pend})")
        print(f"    같은 보고서의 앞선·같은 날 접수: {originals or '없음'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
