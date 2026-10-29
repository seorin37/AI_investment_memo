#!/usr/bin/env python3
"""Synchronize all KOSPI stock identities from one KRX trading-day snapshot."""

from __future__ import annotations

import argparse
import json
from datetime import date

from pipelines.market.stock_master import load_kospi_symbols, sync_kospi_stocks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trade-date",
        required=True,
        type=date.fromisoformat,
        help="KRX 기준 거래일 (YYYY-MM-DD). 휴장일이나 미제공일은 실패 처리합니다.",
    )
    parser.add_argument(
        "--minimum-count",
        type=int,
        default=500,
        help="완전한 KOSPI 스냅샷으로 인정할 최소 종목 수 (기본 500)",
    )
    parser.add_argument(
        "--minimum-existing-ratio",
        type=float,
        default=0.8,
        help="기존 KOSPI 종목 수 대비 최소 응답 비율 (기본 0.8)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        existing_count = len(load_kospi_symbols())
    except ValueError:
        existing_count = 0
    result = sync_kospi_stocks(
        args.trade_date,
        minimum_count=args.minimum_count,
        existing_count=existing_count,
        minimum_existing_ratio=args.minimum_existing_ratio,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
