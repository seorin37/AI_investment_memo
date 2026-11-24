#!/usr/bin/env python3
"""Copy common-stock descriptions to preferred stocks that are still blank.

The default mode is a read-only dry run. Database writes require ``--apply``.
Existing nonblank preferred-stock descriptions are never overwritten. The
preferred-to-common mapping reuses ``pipelines.updates.preferred.build_map``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from pipelines.common.db import database_url, read_database_url
from pipelines.updates.preferred import build_map, is_preferred


STOCKS_SQL = text(
    """
    SELECT btrim(symbol) AS symbol, name, dart_corp_code,
           market::text AS market, description
    FROM stocks
    ORDER BY symbol
    """
)


@dataclass(frozen=True)
class Stock:
    symbol: str
    name: str
    dart_corp_code: str | None
    market: str | None
    description: str | None

    @property
    def has_description(self) -> bool:
        return bool((self.description or "").strip())


def build_plan(stocks: list[Stock]) -> tuple[list[tuple[str, str]], dict[str, object]]:
    """Return ``(preferred, common)`` updates and a diagnostic summary."""

    mapping_input = [
        (stock.symbol, stock.name, stock.dart_corp_code, stock.market)
        for stock in stocks
    ]
    mapping, mapping_rows = build_map(mapping_input)
    by_symbol = {stock.symbol: stock for stock in stocks}
    preferred = [stock for stock in stocks if is_preferred(stock.name)]
    updates: list[tuple[str, str]] = []
    source_missing: list[dict[str, str | None]] = []
    unmapped: list[dict[str, str | None]] = []
    already_matching = 0
    nonblank_different: list[dict[str, str | None]] = []

    for stock in preferred:
        common_symbol = mapping.get(stock.symbol)
        if not common_symbol:
            unmapped.append({"symbol": stock.symbol, "name": stock.name})
            continue
        common = by_symbol[common_symbol]
        if not common.has_description:
            source_missing.append(
                {
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "common": common.symbol,
                    "common_name": common.name,
                }
            )
            continue
        if not stock.has_description:
            updates.append((stock.symbol, common.symbol))
        elif stock.description == common.description:
            already_matching += 1
        else:
            nonblank_different.append(
                {
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "common": common.symbol,
                    "common_name": common.name,
                }
            )

    status_counts: dict[str, int] = {}
    for row in mapping_rows:
        status = str(row["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    summary: dict[str, object] = {
        "stocks": len(stocks),
        "preferred_total": len(preferred),
        "mapped": len(mapping),
        "mapping_status": status_counts,
        "blank_preferred": sum(not stock.has_description for stock in preferred),
        "already_matching": already_matching,
        "nonblank_different": nonblank_different,
        "unmapped": unmapped,
        "source_missing": source_missing,
        "update_candidates": len(updates),
        "blank_nonpreferred": [
            {"symbol": stock.symbol, "name": stock.name}
            for stock in stocks
            if not is_preferred(stock.name) and not stock.has_description
        ],
    }
    return updates, summary


def load_stocks(connection) -> list[Stock]:
    return [Stock(**dict(row)) for row in connection.execute(STOCKS_SQL).mappings()]


def run(*, engine: Engine, apply: bool) -> dict[str, object]:
    update_sql = text(
        """
        UPDATE stocks AS preferred
        SET description = common.description,
            updated_at = now()
        FROM stocks AS common
        WHERE preferred.symbol = :preferred_symbol
          AND common.symbol = :common_symbol
          AND NULLIF(btrim(preferred.description), '') IS NULL
          AND NULLIF(btrim(common.description), '') IS NOT NULL
        """
    )
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            stocks_before = load_stocks(connection)
            updates, summary = build_plan(stocks_before)
            result: dict[str, object] = {
                "mode": "apply" if apply else "dry-run",
                **summary,
                "updated_rows": 0,
                "post_verified_rows": 0,
                "remaining_blank_stocks": sum(
                    not stock.has_description for stock in stocks_before
                ),
            }
            if not apply:
                transaction.rollback()
                return result

            updated = 0
            for preferred_symbol, common_symbol in updates:
                execution = connection.execute(
                    update_sql,
                    {
                        "preferred_symbol": preferred_symbol,
                        "common_symbol": common_symbol,
                    },
                )
                updated += execution.rowcount
            result["updated_rows"] = updated
            if updated != len(updates):
                raise RuntimeError(
                    f"예상 갱신 {len(updates)}건과 실제 갱신 {updated}건이 달라 롤백합니다."
                )

            symbols = [preferred_symbol for preferred_symbol, _ in updates]
            if symbols:
                stocks_after = load_stocks(connection)
                after_by_symbol = {stock.symbol: stock for stock in stocks_after}
                verified = sum(
                    after_by_symbol[preferred_symbol].description
                    == after_by_symbol[common_symbol].description
                    for preferred_symbol, common_symbol in updates
                )
                result["post_verified_rows"] = verified
                result["remaining_blank_stocks"] = sum(
                    not stock.has_description for stock in stocks_after
                )
                if verified != len(updates):
                    raise RuntimeError(
                        "갱신 후 본주와 설명이 일치하지 않는 우선주가 있어 롤백합니다."
                    )
            transaction.commit()
            return result
        except Exception:
            if transaction.is_active:
                transaction.rollback()
            raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="빈 우선주 설명을 DATABASE_URL에 실제 반영",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    url = database_url() if args.apply else read_database_url()
    engine = create_engine(url, pool_pre_ping=True)
    try:
        result = run(engine=engine, apply=args.apply)
    finally:
        engine.dispose()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
