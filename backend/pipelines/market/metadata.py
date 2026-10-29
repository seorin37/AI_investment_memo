"""KRX daily market-cap/listed-share enrichment for KIS price rows.

The KRX response is fetched once per trading date.  Only the pilot symbols and
only MKTCAP/LIST_SHRS are used; KRX OHLCV is deliberately ignored.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Callable, Iterable

from sqlalchemy import bindparam, text

from pipelines.common.db import get_engine
from pipelines.market.calendar import is_krx_trading_day
from pipelines.market.kis import PILOT_SYMBOLS, assert_kis_schema
from pipelines.market.krx import fetch_kospi_daily


SOURCE = "KRX_OPEN_API"
Fetcher = Callable[[date], list[dict]]


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


def normalize_market_metadata(row: dict) -> dict:
    if row.get("MKT_NM") != "KOSPI":
        raise ValueError("KOSPI 메타데이터가 아닙니다.")
    symbol = str(row.get("ISU_CD", "")).strip()
    if symbol not in PILOT_SYMBOLS:
        raise ValueError("파일럿 종목이 아닙니다.")
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
    symbols: Iterable[str] = PILOT_SYMBOLS,
    fetcher: Fetcher = fetch_kospi_daily,
) -> list[dict]:
    """Call the all-KOSPI endpoint once and retain only requested pilots."""
    requested = set(symbols)
    if requested - set(PILOT_SYMBOLS):
        raise ValueError("현재는 파일럿 4종목만 지원합니다.")
    raw_rows = fetcher(trade_date)
    selected = [
        normalize_market_metadata(row)
        for row in raw_rows
        if str(row.get("ISU_CD", "")).strip() in requested
        and row.get("MKT_NM") == "KOSPI"
    ]
    if raw_rows and len(selected) != len(requested):
        found = {row["symbol"] for row in selected}
        missing = sorted(requested - found)
        raise ValueError(f"KRX 응답에 파일럿 종목이 없습니다: {', '.join(missing)}")
    return selected


def save_market_metadata(rows: list[dict]) -> dict:
    """Enrich existing KIS price rows; never create metadata-only price rows."""
    if not rows:
        return {"updated_rows": 0, "deferred_keys": []}
    dates = {row["trade_date"] for row in rows}
    if len(dates) != 1:
        raise ValueError("메타데이터 저장은 한 거래일씩 수행해야 합니다.")
    trade_date = next(iter(dates))
    symbols = [row["symbol"] for row in rows]
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
        """
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
        if update_rows:
            connection.execute(update_statement, update_rows)
    deferred = [
        f"{row['symbol']}:{row['trade_date'].isoformat()}"
        for row in rows
        if row["symbol"] not in existing
    ]
    return {"updated_rows": len(update_rows), "deferred_keys": deferred}


def backfill_market_metadata(
    start_date: date,
    end_date: date,
    *,
    symbols: Iterable[str] = PILOT_SYMBOLS,
    request_interval: float = 0.5,
    fetcher: Fetcher = fetch_kospi_daily,
    saver: Callable[[list[dict]], dict] = save_market_metadata,
    check_schema: bool = True,
) -> dict:
    if start_date > end_date or request_interval < 0:
        raise ValueError("수집 날짜 또는 요청 간격이 올바르지 않습니다.")
    if check_schema:
        assert_kis_schema()
    result = {
        "success_dates": 0,
        "skipped_holidays": 0,
        "failed_dates": [],
        "errors": {},
        "updated_rows": 0,
        "deferred_keys": [],
    }
    cursor = start_date
    while cursor <= end_date:
        if not is_krx_trading_day(cursor):
            result["skipped_holidays"] += 1
            cursor += timedelta(days=1)
            continue
        try:
            rows = fetch_market_metadata(cursor, symbols=symbols, fetcher=fetcher)
            if not rows:
                raise ValueError("KRX KOSPI 일별 응답이 비어 있습니다.")
            saved = saver(rows)
            result["success_dates"] += 1
            result["updated_rows"] += saved["updated_rows"]
            result["deferred_keys"].extend(saved["deferred_keys"])
        except Exception as exc:
            result["failed_dates"].append(cursor.isoformat())
            result["errors"][cursor.isoformat()] = type(exc).__name__
        cursor += timedelta(days=1)
        if cursor <= end_date and request_interval:
            time.sleep(request_interval)
    return result
