#!/usr/bin/env python3
"""DB에 등록된 KOSPI 종목의 KIS 원시·수정 일봉 백필 진입점.

0011 migration 적용 후에만 실행한다. 기간을 반드시 명시해야 하며 원시와
수정 OHLCV를 함께 수집한다. 주문·계좌 API는 사용하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from pipelines.daily_refresh import daily_refresh_lock
from pipelines.market.kis import (
    KisClient,
    KOSPI_BACKFILL_STATE_ROOT,
    assert_kis_schema,
    backfill_kis_prices,
)
from pipelines.market.metadata import backfill_market_metadata
from pipelines.market.stock_master import load_kospi_symbols


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="테스트·제한 실행용 명시 종목. 생략하면 DB의 KOSPI 전체",
    )
    parser.add_argument(
        "--symbol-limit",
        type=int,
        help="테스트·제한 실행용 최대 종목 수",
    )
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--adjusted-only", action="store_true")
    parser.add_argument("--krx-request-interval", type=float, default=0.5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with daily_refresh_lock() as acquired:
        if not acquired:
            print(
                json.dumps(
                    {
                        "status": "skipped_concurrent",
                        "error": "다른 시장데이터 수집 작업이 실행 중입니다.",
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 2
        targets = load_kospi_symbols(
            symbols=args.symbols,
            limit=args.symbol_limit,
        )
        assert_kis_schema()
        with KisClient() as client:
            result = backfill_kis_prices(
                start_date=args.start,
                end_date=args.end,
                symbols=targets,
                client=client,
                include_raw=not args.adjusted_only,
                include_adjusted=True,
                resume=not args.no_resume,
                state_root=KOSPI_BACKFILL_STATE_ROOT,
            )
            if not args.adjusted_only:
                result["market_metadata"] = backfill_market_metadata(
                    args.start,
                    args.end,
                    symbols=targets,
                    request_interval=args.krx_request_interval,
                    check_schema=False,
                )
            result["kis_request_metrics"] = {
                **client.request_metrics(),
                "request_interval_seconds": client.request_interval,
                "rate_limit_cooldown_seconds": client.rate_limit_cooldown,
            }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    failed = bool(
        result["failed_symbols"]
        or (result.get("market_metadata") or {}).get("failed_dates")
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
