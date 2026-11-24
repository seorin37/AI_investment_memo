#!/usr/bin/env python3
"""Validate a reviewed company-overview CSV and update ``stocks.description``.

The default mode is a read-only dry run.  Database writes require ``--apply``
and use ``DATABASE_URL``; dry runs prefer ``READONLY_DATABASE_URL``.  The
entire update is performed in one transaction and any validation or
post-update mismatch rolls it back.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine

from pipelines.common.db import database_url, read_database_url


DEFAULT_INPUT = Path("data/company_overview_20261115/company_overviews_verified.csv")
SYMBOL_RE = re.compile(r"^[0-9A-Z]{6}$")
MIN_DESCRIPTION_LENGTH = 80
MAX_DESCRIPTION_LENGTH = 180


@dataclass(frozen=True)
class OverviewRow:
    symbol: str
    name: str
    description: str
    verdict: str

    @property
    def is_blank(self) -> bool:
        return self.verdict == "blank"


def load_rows(path: Path, *, expected_rows: int = 825) -> list[OverviewRow]:
    """Read and fully validate the artifact before any DB connection."""

    if not path.is_file():
        raise ValueError(f"입력 CSV가 없습니다: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"symbol", "name", "description"}
        missing_columns = sorted(required - set(reader.fieldnames or ()))
        if missing_columns:
            raise ValueError("입력 CSV 필수 열이 없습니다: " + ", ".join(missing_columns))
        records = list(reader)

    if len(records) != expected_rows:
        raise ValueError(
            f"입력 CSV 행 수가 올바르지 않습니다: {len(records)}건, 예상 {expected_rows}건"
        )

    rows: list[OverviewRow] = []
    seen: set[str] = set()
    for line_no, record in enumerate(records, start=2):
        symbol = (record.get("symbol") or "").strip()
        name = (record.get("name") or "").strip()
        description = (record.get("description") or "").strip()
        verdict = (record.get("verdict") or "ok").strip().lower()
        if not SYMBOL_RE.fullmatch(symbol):
            raise ValueError(f"{line_no}행 종목코드가 올바르지 않습니다: {symbol!r}")
        if symbol in seen:
            raise ValueError(f"입력 CSV 종목코드가 중복됐습니다: {symbol}")
        seen.add(symbol)
        if not name:
            raise ValueError(f"{line_no}행 회사명이 비어 있습니다: {symbol}")
        if verdict not in {"ok", "fixed", "blank", "pilot"}:
            raise ValueError(f"{line_no}행 verdict가 올바르지 않습니다: {verdict!r}")
        if verdict == "blank":
            if description:
                raise ValueError(f"{line_no}행 blank 판정에 설명이 남아 있습니다: {symbol}")
        elif not description:
            raise ValueError(f"{line_no}행 설명이 비어 있습니다: {symbol}")
        elif not MIN_DESCRIPTION_LENGTH <= len(description) <= MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"{line_no}행 설명 길이가 범위를 벗어났습니다: "
                f"{symbol} {len(description)}자"
            )
        rows.append(OverviewRow(symbol, name, description, verdict))
    return rows


def _load_stocks(connection, symbols: Iterable[str]) -> dict[str, dict[str, str | None]]:
    statement = text(
        "SELECT symbol, name, description FROM stocks WHERE symbol IN :symbols"
    ).bindparams(bindparam("symbols", expanding=True))
    return {
        str(row["symbol"]).strip(): {
            "name": str(row["name"]).strip(),
            "description": row["description"],
        }
        for row in connection.execute(
            statement, {"symbols": list(symbols)}
        ).mappings()
    }


def build_plan(
    rows: Iterable[OverviewRow],
    stocks: dict[str, dict[str, str | None]],
) -> tuple[list[OverviewRow], dict[str, int]]:
    """Validate DB identities and return rows whose descriptions must change."""

    values = list(rows)
    missing = sorted(row.symbol for row in values if row.symbol not in stocks)
    if missing:
        raise ValueError("DB stocks에 없는 종목코드: " + ", ".join(missing))
    mismatches = [
        f"{row.symbol} CSV={row.name!r} DB={stocks[row.symbol]['name']!r}"
        for row in values
        if stocks[row.symbol]["name"] != row.name
    ]
    if mismatches:
        raise ValueError("회사명 불일치:\n- " + "\n- ".join(mismatches))

    applicable = [row for row in values if not row.is_blank]
    changes = [
        row
        for row in applicable
        if stocks[row.symbol]["description"] != row.description
    ]
    return changes, {
        "input_rows": len(values),
        "db_matched_rows": len(stocks),
        "blank_skipped": len(values) - len(applicable),
        "already_unchanged": len(applicable) - len(changes),
        "update_candidates": len(changes),
    }


def run(rows: list[OverviewRow], *, engine: Engine, apply: bool) -> dict[str, object]:
    """Plan or apply the update.  ``--apply`` is the only write path."""

    symbols = [row.symbol for row in rows]
    update_statement = text(
        """
        UPDATE stocks
        SET description = :description,
            updated_at = now()
        WHERE symbol = :symbol
          AND description IS DISTINCT FROM :description
        """
    )
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            stocks_before = _load_stocks(connection, symbols)
            changes, counts = build_plan(rows, stocks_before)
            result: dict[str, object] = {
                "mode": "apply" if apply else "dry-run",
                **counts,
                "updated_rows": 0,
                "post_verified_rows": 0,
            }
            if not apply:
                transaction.rollback()
                return result

            if changes:
                update_result = connection.execute(
                    update_statement,
                    [
                        {"symbol": row.symbol, "description": row.description}
                        for row in changes
                    ],
                )
                result["updated_rows"] = update_result.rowcount
                stocks_after = _load_stocks(
                    connection, (row.symbol for row in changes)
                )
                verified = sum(
                    stocks_after[row.symbol]["description"] == row.description
                    for row in changes
                )
                result["post_verified_rows"] = verified
                if update_result.rowcount != len(changes) or verified != len(changes):
                    raise RuntimeError(
                        "갱신 후 검증 건수가 일치하지 않아 트랜잭션을 롤백합니다: "
                        f"후보 {len(changes)}, UPDATE {update_result.rowcount}, 검증 {verified}"
                    )
            transaction.commit()
            return result
        except Exception:
            if transaction.is_active:
                transaction.rollback()
            raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--expected-rows", type=int, default=825)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="검증을 통과한 변경을 DATABASE_URL의 stocks에 실제 반영",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.expected_rows < 1:
        raise ValueError("--expected-rows는 1 이상이어야 합니다.")
    rows = load_rows(args.input, expected_rows=args.expected_rows)
    url = database_url() if args.apply else read_database_url()
    engine = create_engine(url, pool_pre_ping=True)
    try:
        summary = run(rows, engine=engine, apply=args.apply)
    finally:
        engine.dispose()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
