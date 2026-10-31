#!/usr/bin/env python3
"""Fill only missing KRX market metadata on existing KIS price rows.

This command never fetches or writes OHLCV.  For each DB date with missing
metadata it queries KOSPI once, and queries KOSDAQ once only when one or more
requested symbols were not present in the KOSPI response.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import date

from sqlalchemy import bindparam, text

from pipelines.common.db import get_engine
from pipelines.daily_refresh import daily_refresh_lock
from pipelines.market.kis import assert_kis_schema
from pipelines.market.metadata import fetch_market_metadata, save_market_metadata
from pipelines.market.stock_master import load_kospi_symbols


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--request-interval", type=float, default=0.5)
    return parser.parse_args()


def load_missing_keys(
    start_date: date,
    end_date: date,
    symbols: tuple[str, ...],
) -> dict[date, tuple[str, ...]]:
    statement = text(
        """
        SELECT trade_date, symbol
        FROM prices_daily
        WHERE source = 'KIS'
          AND trade_date BETWEEN :start_date AND :end_date
          AND symbol IN :symbols
          AND (
            market_cap IS NULL
            OR listed_shares IS NULL
            OR market_metadata_source IS NULL
          )
        ORDER BY trade_date, symbol
        """
    ).bindparams(bindparam("symbols", expanding=True))
    grouped: dict[date, list[str]] = defaultdict(list)
    with get_engine().connect() as connection:
        for row in connection.execute(
            statement,
            {
                "start_date": start_date,
                "end_date": end_date,
                "symbols": list(symbols),
            },
        ).mappings():
            grouped[row["trade_date"]].append(row["symbol"])
    return {day: tuple(values) for day, values in grouped.items()}


def main() -> int:
    args = parse_args()
    if args.start > args.end or args.request_interval < 0:
        raise ValueError("Invalid date range or request interval.")
    targets = load_kospi_symbols(symbols=args.symbols)
    assert_kis_schema()
    with daily_refresh_lock() as acquired:
        if not acquired:
            print(json.dumps({"status": "skipped_concurrent"}))
            return 2
        missing_by_date = load_missing_keys(args.start, args.end, targets)
        summary = {
            "target_rows": sum(map(len, missing_by_date.values())),
            "target_dates": len(missing_by_date),
            "updated_rows": 0,
            "still_missing_keys": [],
            "failed_dates": {},
        }
        if (
            args.expected_count is not None
            and summary["target_rows"] != args.expected_count
        ):
            print(json.dumps({
                **summary,
                "status": "expected_count_mismatch",
                "expected_count": args.expected_count,
            }, ensure_ascii=False, indent=2))
            return 3
        dates = sorted(missing_by_date)
        for index, trade_date in enumerate(dates):
            try:
                rows = fetch_market_metadata(
                    trade_date,
                    symbols=missing_by_date[trade_date],
                )
                saved = save_market_metadata(rows, missing_only=True)
                summary["updated_rows"] += saved["updated_rows"]
                summary["still_missing_keys"].extend(
                    f"{symbol}:{trade_date.isoformat()}"
                    for symbol in rows.missing_symbols
                )
            except Exception as exc:
                summary["failed_dates"][trade_date.isoformat()] = {
                    "stage": "KOSPI_PRIMARY_OR_SAVE",
                    "type": type(exc).__name__,
                }
            else:
                if rows.fallback_error is not None:
                    summary["failed_dates"][trade_date.isoformat()] = {
                        "stage": "KOSDAQ_FALLBACK",
                        "type": type(rows.fallback_error).__name__,
                    }
            if index + 1 < len(dates) and args.request_interval:
                time.sleep(args.request_interval)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["failed_dates"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
