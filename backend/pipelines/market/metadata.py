"""KRX daily market-cap/listed-share enrichment for KIS price rows.

The KRX response is fetched once per trading date.  Only the DB-managed KOSPI
universe and MKTCAP/LIST_SHRS are used; KRX OHLCV is deliberately ignored.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Callable, Iterable

from sqlalchemy import bindparam, text

from pipelines.common.db import get_engine
from pipelines.market.calendar import is_krx_trading_day
from pipelines.market.kis import assert_kis_schema
from pipelines.market.krx import (
    fetch_kosdaq_daily,
    fetch_kospi_daily,
    is_valid_stock_symbol,
)
from pipelines.market.stock_master import load_kospi_symbols


SOURCE = "KRX_OPEN_API"
Fetcher = Callable[[date], list[dict]]


class MarketMetadataRows(list[dict]):
    """Normalized rows plus diagnostics for the KOSDAQ fallback."""

    def __init__(
        self,
        rows: Iterable[dict],
        *,
        fallback_attempted: bool = False,
        fallback_rows: int = 0,
        missing_symbols: Iterable[str] = (),
        fallback_error: Exception | None = None,
    ) -> None:
        super().__init__(rows)
        self.fallback_attempted = fallback_attempted
        self.fallback_rows = fallback_rows
        self.missing_symbols = tuple(missing_symbols)
        self.fallback_error = fallback_error


def _target_symbols(symbols: Iterable[str]) -> tuple[str, ...]:
    targets = tuple(str(symbol).strip() for symbol in symbols)
    if not targets:
        raise ValueError("KRX 메타데이터 수집 대상이 0종목입니다.")
    if len(targets) != len(set(targets)):
        raise ValueError("KRX 메타데이터 수집 대상에 중복 종목이 있습니다.")
    if any(not is_valid_stock_symbol(symbol) for symbol in targets):
        raise ValueError(
            "KRX 메타데이터 종목코드는 6자리 영문 대문자 또는 숫자여야 합니다."
        )
    return targets


def _decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value or "").replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValueError(f"{field} 값이 숫자가 아닙니다.") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{field} 값은 0 이상의 유한수여야 합니다.")
    return parsed


def _integer(value: object, field: str) -> int:
    parsed = _decimal(value, field)
    if parsed != parsed.to_integral_value():
        raise ValueError(f"{field} 값이 정수가 아닙니다.")
    result = int(parsed)
    if result <= 0:
        raise ValueError(f"{field} 값은 양수여야 합니다.")
    return result


def normalize_market_metadata(row: dict, *, expected_market: str = "KOSPI") -> dict:
    if row.get("MKT_NM") != expected_market:
        raise ValueError(f"{expected_market} 메타데이터가 아닙니다.")
    symbol = str(row.get("ISU_CD", "")).strip()
    if not is_valid_stock_symbol(symbol):
        raise ValueError("종목코드는 6자리 영문 대문자 또는 숫자여야 합니다.")
    try:
        trade_date = datetime.strptime(str(row.get("BAS_DD", "")), "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError("KRX 기준일 형식이 올바르지 않습니다.") from exc
    return {
        "symbol": symbol,
        "trade_date": trade_date,
        "market_cap": _decimal(row.get("MKTCAP"), "시가총액"),
        "listed_shares": _integer(row.get("LIST_SHRS"), "상장주식수"),
        "market_metadata_source": SOURCE,
    }


def fetch_market_metadata(
    trade_date: date,
    *,
    symbols: Iterable[str] | None = None,
    fetcher: Fetcher = fetch_kospi_daily,
    kosdaq_fetcher: Fetcher = fetch_kosdaq_daily,
) -> MarketMetadataRows:
    """Fetch KOSPI metadata, then use one KOSDAQ request for missing symbols."""
    targets = _target_symbols(
        load_kospi_symbols() if symbols is None else symbols
    )
    requested = set(targets)
    raw_rows = fetcher(trade_date)
    if not raw_rows:
        raise ValueError("KRX KOSPI daily response is empty.")
    selected = []
    found: set[str] = set()
    for row in raw_rows:
        symbol = str(row.get("ISU_CD", "")).strip()
        if symbol not in requested or row.get("MKT_NM") != "KOSPI":
            continue
        normalized = normalize_market_metadata(row)
        if normalized["trade_date"] != trade_date:
            raise ValueError("KRX 응답 기준일이 요청일과 일치하지 않습니다.")
        if symbol in found:
            raise ValueError(f"KRX 응답에 중복 종목이 있습니다: {symbol}")
        found.add(symbol)
        selected.append(normalized)
    missing = requested - found
    if not missing:
        return MarketMetadataRows(selected)

    try:
        kosdaq_rows = kosdaq_fetcher(trade_date)
    except Exception as exc:
        return MarketMetadataRows(
            selected,
            fallback_attempted=True,
            missing_symbols=sorted(missing),
            fallback_error=exc,
        )

    fallback_count = 0
    try:
        for row in kosdaq_rows:
            symbol = str(row.get("ISU_CD", "")).strip()
            if symbol not in missing or row.get("MKT_NM") != "KOSDAQ":
                continue
            normalized = normalize_market_metadata(row, expected_market="KOSDAQ")
            if normalized["trade_date"] != trade_date:
                raise ValueError("KRX response date does not match the requested date.")
            if symbol in found:
                raise ValueError(f"KRX response contains a duplicate symbol: {symbol}")
            found.add(symbol)
            selected.append(normalized)
            fallback_count += 1
    except Exception as exc:
        return MarketMetadataRows(
            selected,
            fallback_attempted=True,
            fallback_rows=fallback_count,
            missing_symbols=sorted(requested - found),
            fallback_error=exc,
        )

    return MarketMetadataRows(
        selected,
        fallback_attempted=True,
        fallback_rows=fallback_count,
        missing_symbols=sorted(requested - found),
    )


def save_market_metadata(rows: list[dict], *, missing_only: bool = False) -> dict:
    """Enrich existing KIS price rows; never create metadata-only price rows."""
    if not rows:
        return {"updated_rows": 0, "deferred_keys": []}
    dates = {row["trade_date"] for row in rows}
    if len(dates) != 1:
        raise ValueError("메타데이터 저장은 한 거래일씩 수행해야 합니다.")
    trade_date = next(iter(dates))
    symbols = [row["symbol"] for row in rows]
    if len(symbols) != len(set(symbols)):
        raise ValueError("메타데이터 저장 대상에 중복 종목이 있습니다.")
    missing_clause = (
        """
          AND (
            market_cap IS NULL
            OR listed_shares IS NULL
            OR market_metadata_source IS NULL
          )
        """
        if missing_only
        else ""
    )
    select_statement = text(
        """
        SELECT symbol
        FROM prices_daily
        WHERE trade_date = :trade_date
          AND source = 'KIS'
          AND symbol IN :symbols
        """
    ).bindparams(bindparam("symbols", expanding=True))
    update_statement = text(
        """
        UPDATE prices_daily
        SET market_cap = :market_cap,
            listed_shares = :listed_shares,
            market_metadata_source = :market_metadata_source
        WHERE symbol = :symbol
          AND trade_date = :trade_date
          AND source = 'KIS'
          AND (
            market_cap IS DISTINCT FROM :market_cap
            OR listed_shares IS DISTINCT FROM :listed_shares
            OR market_metadata_source IS DISTINCT FROM :market_metadata_source
          )
        """ + missing_clause
    )
    engine = get_engine()
    with engine.begin() as connection:
        existing = {
            str(value).strip()
            for value in connection.execute(
                select_statement,
                {"trade_date": trade_date, "symbols": symbols},
            ).scalars()
        }
        update_rows = [row for row in rows if row["symbol"] in existing]
        updated_rows = 0
        if update_rows:
            update_result = connection.execute(update_statement, update_rows)
            rowcount = getattr(update_result, "rowcount", None)
            updated_rows = (
                rowcount
                if isinstance(rowcount, int) and rowcount >= 0
                else len(update_rows)
            )
    deferred = [
        f"{row['symbol']}:{row['trade_date'].isoformat()}"
        for row in rows
        if row["symbol"] not in existing
    ]
    return {"updated_rows": updated_rows, "deferred_keys": deferred}


def backfill_market_metadata(
    start_date: date,
    end_date: date,
    *,
    symbols: Iterable[str] | None = None,
    request_interval: float = 0.5,
    fetcher: Fetcher = fetch_kospi_daily,
    kosdaq_fetcher: Fetcher = fetch_kosdaq_daily,
    saver: Callable[[list[dict]], dict] = save_market_metadata,
    check_schema: bool = True,
) -> dict:
    if start_date > end_date or request_interval < 0:
        raise ValueError("수집 날짜 또는 요청 간격이 올바르지 않습니다.")
    targets = _target_symbols(
        load_kospi_symbols() if symbols is None else symbols
    )
    if check_schema:
        assert_kis_schema()
    result = {
        "success_dates": 0,
        "skipped_holidays": 0,
        "failed_dates": [],
        "errors": {},
        "target_count": len(targets),
        "processed_target_dates": 0,
        "response_rows": 0,
        "updated_rows": 0,
        "deferred_keys": [],
        "missing_keys": [],
        "kosdaq_fallback_dates": [],
        "kosdaq_fallback_rows": 0,
        "kosdaq_fallback_failed_dates": [],
        "partial_dates": [],
    }
    cursor = start_date
    while cursor <= end_date:
        if not is_krx_trading_day(cursor):
            result["skipped_holidays"] += 1
            cursor += timedelta(days=1)
            continue
        try:
            rows = fetch_market_metadata(
                cursor,
                symbols=targets,
                fetcher=fetcher,
                kosdaq_fetcher=kosdaq_fetcher,
            )
            if not rows and not rows.fallback_attempted:
                raise ValueError("KRX KOSPI 일별 응답이 비어 있습니다.")
            found = {row["symbol"] for row in rows}
            result["processed_target_dates"] += len(targets)
            result["response_rows"] += len(rows)
            result["missing_keys"].extend(
                f"{symbol}:{cursor.isoformat()}"
                for symbol in targets
                if symbol not in found
            )
            saved = saver(rows)
            result["updated_rows"] += saved["updated_rows"]
            result["deferred_keys"].extend(saved["deferred_keys"])
            if rows.fallback_attempted:
                result["kosdaq_fallback_dates"].append(cursor.isoformat())
                result["kosdaq_fallback_rows"] += rows.fallback_rows
            if rows.fallback_error is not None:
                day = cursor.isoformat()
                result["failed_dates"].append(day)
                result["kosdaq_fallback_failed_dates"].append(day)
                result["partial_dates"].append(day)
                result["errors"][day] = {
                    "stage": "KOSDAQ_FALLBACK",
                    "type": type(rows.fallback_error).__name__,
                }
            else:
                result["success_dates"] += 1
        except Exception as exc:
            result["failed_dates"].append(cursor.isoformat())
            result["errors"][cursor.isoformat()] = type(exc).__name__
        cursor += timedelta(days=1)
        if cursor <= end_date and request_interval:
            time.sleep(request_interval)
    result["updated_count"] = result["updated_rows"]
    result["deferred_count"] = len(result["deferred_keys"])
    result["missing_count"] = len(result["missing_keys"])
    return result
