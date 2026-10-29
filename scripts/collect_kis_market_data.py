#!/usr/bin/env python3
"""파일럿 4종목 KIS 원시·수정 일봉 백필 진입점.

0011 migration 적용 후에만 실행한다. 기본 동작은 2020-01-01 이후 원시와
수정 OHLCV를 함께 수집하며 주문·계좌 API는 사용하지 않는다.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

from pipelines.market.kis import (
    BACKFILL_START,
    KisClient,
    PILOT_SYMBOLS,
    assert_kis_schema,
    backfill_kis_prices,
    collect_fundamentals,
    fetch_daily_range,
)
from pipelines.market.metadata import backfill_market_metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=BACKFILL_START)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--symbols", nargs="+", default=list(PILOT_SYMBOLS))
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--adjusted-only", action="store_true")
    parser.add_argument("--krx-request-interval", type=float, default=0.5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    assert_kis_schema()
    latest_raw = {}
    with KisClient() as client:
        result = backfill_kis_prices(
            start_date=args.start,
            end_date=args.end,
            symbols=args.symbols,
            client=client,
            include_raw=not args.adjusted_only,
            include_adjusted=True,
            resume=not args.no_resume,
            capture_latest_raw=latest_raw,
        )
        if not args.adjusted_only:
            for symbol in args.symbols:
                if symbol not in latest_raw:
                    rows, _ = fetch_daily_range(
                        client,
                        symbol,
                        max(args.start, args.end - timedelta(days=14)),
                        args.end,
                        adjusted=False,
                    )
                    if rows:
                        latest_raw[symbol] = rows[-1]
            result["fundamentals"] = collect_fundamentals(
                client, args.symbols, latest_raw
            )
            result["market_metadata"] = backfill_market_metadata(
                args.start,
                args.end,
                symbols=args.symbols,
                request_interval=args.krx_request_interval,
                check_schema=False,
            )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    failed = bool(
        result["failed_symbols"]
        or (result.get("fundamentals") or {}).get("failed_symbols")
        or (result.get("market_metadata") or {}).get("failed_dates")
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
