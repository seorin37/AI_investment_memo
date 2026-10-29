"""KOSPI stock-master synchronization backed by KRX basic information.

The KRX KOSPI stock-basic-information endpoint returns the listed stock master
for one reference date.  This module extracts only identity fields and UPSERTs
them into ``stocks``.  Rows missing from a later snapshot are preserved so
delistings or market transfers never erase historical price/disclosure data.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Callable, Iterable

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from pipelines.common.db import get_engine
from pipelines.market.krx import (
    fetch_kospi_stock_master,
    is_valid_stock_symbol,
    normalize_kospi_stock,
)


Fetcher = Callable[[date], list[dict]]


def load_kospi_symbols(
    *,
    symbols: Iterable[str] | None = None,
    limit: int | None = None,
    engine: Engine | None = None,
) -> tuple[str, ...]:
    """Freeze the KOSPI collection universe from ``stocks`` once per run.

    Explicit symbols and a limit are intended for tests and controlled
    diagnostics.  Explicit symbols must still exist as KOSPI rows, preventing
    a typo or a non-KOSPI code from reaching the external API.
    """

    if limit is not None and limit < 1:
        raise ValueError("종목 수 제한은 1 이상이어야 합니다.")
    requested = None if symbols is None else tuple(str(value).strip() for value in symbols)
    if requested is not None:
        if not requested:
            raise ValueError("명시한 수집 종목이 비어 있습니다.")
        if len(set(requested)) != len(requested):
            raise ValueError("명시한 수집 종목에 중복이 있습니다.")
        for symbol in requested:
            if not is_valid_stock_symbol(symbol):
                raise ValueError(f"유효하지 않은 종목코드: {symbol}")

    statement = text(
        "SELECT symbol FROM stocks WHERE market = 'KOSPI' ORDER BY symbol"
    )
    target_engine = engine or get_engine()
    with target_engine.connect() as connection:
        available = tuple(
            str(symbol).strip()
            for symbol in connection.execute(statement).scalars()
        )
    if not available:
        raise ValueError(
            "stocks에 KOSPI 수집 대상이 없습니다. 종목 마스터를 먼저 등록하세요."
        )

    if requested is None:
        selected = available
    else:
        available_set = set(available)
        missing = [symbol for symbol in requested if symbol not in available_set]
        if missing:
            raise ValueError(
                "stocks에 없는 KOSPI 종목입니다: " + ", ".join(missing)
            )
        selected = requested
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        raise ValueError("확정된 KOSPI 수집 대상이 0종목입니다.")
    return tuple(selected)


def normalize_kospi_snapshot(rows: Iterable[dict]) -> list[dict]:
    """Normalize and validate a full KOSPI snapshot.

    Non-KOSPI rows are ignored in case a future upstream response contains
    more than one market.  A malformed KOSPI row or duplicate symbol fails the
    whole snapshot so a partial/ambiguous master is never written.
    """

    normalized: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        # The base-info endpoint is KOSPI-specific.  Retain compatibility with
        # the older daily-response normalizer while ignoring a mixed-market
        # row if a caller supplies one in tests or tooling.
        market = (
            row.get("MKT_TP_NM")
            if row.get("ISU_SRT_CD")
            else row.get("MKT_NM")
        )
        if market != "KOSPI":
            continue
        stock = normalize_kospi_stock(row)
        symbol = stock["symbol"]
        if symbol in seen:
            raise ValueError(f"KRX KOSPI 응답에 종목코드가 중복됐습니다: {symbol}")
        seen.add(symbol)
        normalized.append(stock)
    if not normalized:
        raise ValueError("KRX KOSPI 종목 응답이 비어 있습니다.")
    return normalized


def save_kospi_stocks(rows: Iterable[dict], *, engine: Engine | None = None) -> dict:
    """UPSERT KOSPI identities without deleting absent stocks.

    Existing ``sector``, DART mapping, description and share metadata are
    preserved.  New rows rely on the schema's ``sector='general'`` default
    because the KRX basic-information endpoint does not provide the project's
    ``general``/``financial`` sector classification.
    """

    values = list(rows)
    if not values:
        raise ValueError("저장할 KOSPI 종목이 없습니다.")
    symbols: list[str] = []
    seen: set[str] = set()
    for row in values:
        symbol = str(row.get("symbol", "")).strip()
        name = str(row.get("name", "")).strip()
        if not is_valid_stock_symbol(symbol):
            raise ValueError(f"유효하지 않은 종목코드: {symbol}")
        if not name or row.get("market") != "KOSPI":
            raise ValueError(f"KOSPI 종목 식별정보가 올바르지 않습니다: {symbol}")
        if symbol in seen:
            raise ValueError(f"저장 대상 종목코드가 중복됐습니다: {symbol}")
        seen.add(symbol)
        symbols.append(symbol)

    select_existing = text(
        """
        SELECT symbol, name, market
        FROM stocks
        WHERE symbol IN :symbols
        """
    ).bindparams(bindparam("symbols", expanding=True))
    select_existing_kospi = text(
        "SELECT symbol FROM stocks WHERE market = 'KOSPI'"
    )
    upsert = text(
        """
        INSERT INTO stocks (symbol, name, market)
        VALUES (:symbol, :name, :market)
        ON CONFLICT (symbol) DO UPDATE SET
          name = EXCLUDED.name,
          market = EXCLUDED.market,
          updated_at = now()
        WHERE stocks.name IS DISTINCT FROM EXCLUDED.name
           OR stocks.market IS DISTINCT FROM EXCLUDED.market
        """
    )

    target_engine = engine or get_engine()
    with target_engine.begin() as connection:
        existing_kospi = {
            str(symbol).strip()
            for symbol in connection.execute(select_existing_kospi).scalars()
        }
        existing = {
            str(row.symbol).strip(): (row.name, row.market)
            for row in connection.execute(
                select_existing, {"symbols": symbols}
            )
        }
        connection.execute(
            upsert,
            [
                {
                    "symbol": str(row["symbol"]).strip(),
                    "name": str(row["name"]).strip(),
                    "market": row["market"],
                }
                for row in values
            ],
        )

    inserted = sum(symbol not in existing for symbol in symbols)
    updated = sum(
        symbol in existing
        and existing[symbol] != (str(row["name"]).strip(), row["market"])
        for symbol, row in zip(symbols, values)
    )
    preserved_absent = sorted(existing_kospi - set(symbols))
    return {
        "received": len(values),
        "inserted": inserted,
        "updated": updated,
        "unchanged": len(values) - inserted - updated,
        "preserved_absent": len(preserved_absent),
        "preserved_absent_symbols": preserved_absent,
    }


def sync_kospi_stocks(
    trade_date: date,
    *,
    fetcher: Fetcher = fetch_kospi_stock_master,
    saver: Callable[[Iterable[dict]], dict] = save_kospi_stocks,
    minimum_count: int = 1,
    existing_count: int = 0,
    minimum_existing_ratio: float = 0.8,
) -> dict:
    """Fetch one trading-day snapshot and safely synchronize ``stocks``."""

    rows = normalize_kospi_snapshot(fetcher(trade_date))
    if minimum_count < 1 or existing_count < 0:
        raise ValueError("KOSPI 종목 스냅샷 검증 기준이 올바르지 않습니다.")
    if not 0 < minimum_existing_ratio <= 1:
        raise ValueError("KOSPI 기존 종목 대비 최소 비율이 올바르지 않습니다.")
    required = max(
        minimum_count,
        math.ceil(existing_count * minimum_existing_ratio),
    )
    if len(rows) < required:
        raise ValueError(
            "KRX KOSPI 종목 응답이 명백히 불완전합니다: "
            f"수신 {len(rows)}건, 최소 {required}건"
        )
    result = saver(rows)
    return {
        "trade_date": trade_date.isoformat(),
        "minimum_required": required,
        "failed_count": 0,
        **result,
    }
