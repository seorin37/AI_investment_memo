"""Operational Friday market finality pipeline.

Friday Capture remains the immutable KIS fundamentals source.  Saturday stores
verified KRX raw prices and confirmed-close fundamentals.  Monday verifies KIS
raw bars against those KRX rows and stores only KIS adjusted bars.

The module is deliberately date-scoped and fail-closed.  Provider responses
are preserved before database writes, completed rows are never overwritten,
and the existing daily-refresh advisory lock is acquired by the CLI wrapper.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from sqlalchemy import bindparam, text

from pipelines.common.db import get_engine
from pipelines.market.calendar import is_krx_trading_day
from pipelines.market.kis import ADJUSTMENT_BASIS, SOURCE as KIS_SOURCE, fetch_daily_range
from pipelines.market.kis_fundamentals import (
    RAW_SNAPSHOT_ROOT,
    analysis_ratios,
    capture_target_symbols,
    load_snapshot,
    normalize_staged_fundamentals,
    verify_raw_daily_against_krx,
)
from pipelines.market.krx import KrxDailySnapshot, fetch_kospi_daily_snapshot, is_valid_stock_symbol, parse_number
from pipelines.market.symbol_status import SymbolStatus, load_symbol_statuses


SEOUL = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).resolve().parents[3]
STATE_ROOT = PROJECT_ROOT / "logs" / "market" / "friday_finality_v1"
SCHEMA_VERSION = 1
KRX_SOURCE = "KRX_OPEN_API"
RAW_READY = "friday_raw_ready"
ADJUSTED_FINALIZED = "friday_adjusted_finalized"
UNVERIFIED_NO_KRX = "unverified_no_krx"
RETRY_REQUIRED = "retry_required"
SATURDAY_WINDOW = (time(7, 55), time(8, 20))
MONDAY_WINDOW = (time(7, 55), time(8, 15))
MONDAY_DEADLINE = time(8, 45)
REQUEST_CAP_EXTRA = 200


class FridayPipelineError(RuntimeError):
    pass


class FridayInputError(FridayPipelineError):
    pass


class FridayConflictError(FridayPipelineError):
    pass


def _iso(value: datetime) -> str:
    return value.astimezone(SEOUL).isoformat()


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: object) -> None:
    _atomic_bytes(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
    )


def _write_once(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise FridayConflictError(f"기존 원본과 새 내용이 다릅니다: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FridayInputError(f"JSON 입력을 읽을 수 없습니다: {path}") from exc
    if not isinstance(value, dict):
        raise FridayInputError(f"JSON 입력이 객체가 아닙니다: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(root: Path, names: Iterable[str]) -> dict[str, str]:
    entries = {name: _sha256(root / name) for name in sorted(set(names))}
    payload = "".join(f"{digest}  {name}\n" for name, digest in entries.items()).encode()
    _atomic_bytes(root / "SHA256SUMS", payload)
    return entries


def verify_manifest(root: Path, required: Iterable[str]) -> dict[str, str]:
    path = root / "SHA256SUMS"
    if not path.is_file():
        raise FridayInputError("금요일 단계 SHA256SUMS가 없습니다.")
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, separator, rel = line.partition("  ")
        candidate = Path(rel)
        if (
            not separator
            or len(digest) != 64
            or candidate.is_absolute()
            or ".." in candidate.parts
        ):
            raise FridayInputError("SHA256SUMS 형식이 올바르지 않습니다.")
        target = root / candidate
        if not target.is_file() or _sha256(target) != digest:
            raise FridayInputError(f"SHA-256 불일치: {rel}")
        entries[rel] = digest
    missing = sorted(set(required) - set(entries))
    if missing:
        raise FridayInputError(f"SHA256SUMS 필수 파일 누락: {missing}")
    return entries


def automatic_trade_date(now: datetime, stage: str) -> date | None:
    local = now.astimezone(SEOUL)
    offsets = {"saturday": (5, 1), "monday": (0, 3)}
    if stage not in offsets:
        raise ValueError("금요일 단계 이름이 올바르지 않습니다.")
    weekday, offset = offsets[stage]
    if local.weekday() != weekday:
        return None
    candidate = local.date() - timedelta(days=offset)
    if candidate.weekday() != 4 or not is_krx_trading_day(candidate):
        return None
    return candidate


def validate_recovery_trade_date(trade_date: date, now: datetime) -> None:
    if (
        trade_date.weekday() != 4
        or not is_krx_trading_day(trade_date)
        or trade_date >= now.astimezone(SEOUL).date()
    ):
        raise FridayInputError("지연 복구는 이미 지난 실제 금요일 거래일만 허용됩니다.")


def within_window(now: datetime, window: tuple[time, time]) -> bool:
    current = now.astimezone(SEOUL).timetz().replace(tzinfo=None)
    return window[0] <= current <= window[1]


def monday_deadline(trade_date: date, now: datetime, *, delayed_recovery: bool) -> datetime:
    local = now.astimezone(SEOUL)
    if delayed_recovery:
        validate_recovery_trade_date(trade_date, now)
        return local + timedelta(minutes=45)
    if automatic_trade_date(now, "monday") != trade_date or not within_window(now, MONDAY_WINDOW):
        raise FridayInputError("월요일 자동 실행 날짜 또는 07:55~08:15 시작 창이 아닙니다.")
    return datetime.combine(local.date(), MONDAY_DEADLINE, tzinfo=SEOUL)


def capture_evidence(capture_root: Path, trade_date: date) -> dict:
    summary_path = capture_root / trade_date.isoformat() / "capture_summary.json"
    targets = capture_target_symbols(capture_root, trade_date)
    summary = _read_json(summary_path)
    invalid = []
    for symbol in targets:
        try:
            load_snapshot(capture_root, trade_date, symbol)
        except Exception:
            invalid.append(symbol)
    if invalid:
        raise FridayInputError(f"Capture 원본 누락 또는 손상: {invalid[:10]}")
    if summary.get("failed_symbols"):
        raise FridayInputError("Capture 실패 종목이 있어 토요일 저장을 시작할 수 없습니다.")
    return {
        "summary_path": str(summary_path),
        "summary_sha256": _sha256(summary_path),
        "target_symbols": list(targets),
        "target_count": len(targets),
        "captured_count": len(summary.get("captured_symbols") or ()),
        "skipped_count": len(summary.get("skipped_symbols") or ()),
    }


def _number(value: object, field: str, *, integer: bool = False) -> Decimal | int:
    parsed = parse_number(value, integer=integer)
    if parsed is None:
        raise FridayInputError(f"KRX {field} 값이 없습니다.")
    return parsed


def normalize_krx_price(row: dict, trade_date: date) -> dict:
    symbol = str(row.get("ISU_CD") or "").strip()
    if row.get("MKT_NM") != "KOSPI" or not is_valid_stock_symbol(symbol):
        raise FridayInputError(f"유효한 KOSPI 종목 행이 아닙니다: {symbol}")
    if str(row.get("BAS_DD") or "") != trade_date.strftime("%Y%m%d"):
        raise FridayInputError(f"KRX 기준일이 다릅니다: {symbol}")
    prices = {
        "open": _number(row.get("TDD_OPNPRC"), "시가"),
        "high": _number(row.get("TDD_HGPRC"), "고가"),
        "low": _number(row.get("TDD_LWPRC"), "저가"),
        "close": _number(row.get("TDD_CLSPRC"), "종가"),
    }
    volume = int(_number(row.get("ACC_TRDVOL"), "거래량", integer=True))
    trade_value = _number(row.get("ACC_TRDVAL"), "거래대금")
    market_cap = _number(row.get("MKTCAP"), "시가총액")
    listed_shares = int(_number(row.get("LIST_SHRS"), "상장주식수", integer=True))
    if volume < 0 or trade_value < 0 or market_cap < 0 or listed_shares <= 0:
        raise FridayInputError(f"KRX 거래량·거래대금·시총·주식수가 유효하지 않습니다: {symbol}")
    if prices["close"] <= 0 or any(value < 0 for value in prices.values()):
        raise FridayInputError(f"KRX 종가 또는 OHLC가 유효하지 않습니다: {symbol}")
    zero_ohl = any(value == 0 for key, value in prices.items() if key != "close")
    if zero_ohl and not (
        volume == 0 and prices["open"] == prices["high"] == prices["low"] == 0
    ):
        raise FridayInputError(f"거래 종목 또는 일부 OHLC만 0입니다: {symbol}")
    if not zero_ohl and (
        prices["high"] < max(prices.values())
        or prices["low"] > min(prices.values())
        or min(prices.values()) <= 0
    ):
        raise FridayInputError(f"KRX OHLC 순서가 유효하지 않습니다: {symbol}")
    return {
        "symbol": symbol,
        "trade_date": trade_date,
        **prices,
        "volume": volume,
        "trade_value": trade_value,
        "market_cap": market_cap,
        "listed_shares": listed_shares,
        "source": KRX_SOURCE,
        "market_metadata_source": KRX_SOURCE,
        "zero_volume": volume == 0,
        "raw": row,
    }


def validate_krx_rows(
    raw_rows: list[dict],
    targets: Iterable[str],
    trade_date: date,
    statuses: dict[str, SymbolStatus],
) -> dict:
    target_list = tuple(targets)
    target_set = set(target_list)
    response_symbols = [
        str(row.get("ISU_CD") or "").strip()
        for row in raw_rows
        if row.get("MKT_NM") == "KOSPI"
    ]
    duplicates = sorted({symbol for symbol in response_symbols if response_symbols.count(symbol) > 1})
    if duplicates:
        raise FridayInputError(f"KRX 중복 종목: {duplicates[:10]}")
    response_set = set(response_symbols)
    extras = sorted(response_set - target_set)
    terminal_targets = {
        symbol for symbol in target_set
        if symbol in statuses and statuses[symbol].is_terminal_on(trade_date)
    }
    missing = sorted(target_set - response_set)
    allowed_missing = sorted(
        symbol
        for symbol in missing
        if symbol in statuses and statuses[symbol].is_terminal_on(trade_date)
    )
    blocking_missing = sorted(set(missing) - set(allowed_missing))
    if extras or blocking_missing:
        raise FridayInputError(
            f"KRX 종목 집합 불일치 extras={extras[:10]} missing={blocking_missing[:10]}"
        )
    by_symbol = {str(row.get("ISU_CD") or "").strip(): row for row in raw_rows}
    normalized = [
        normalize_krx_price(by_symbol[symbol], trade_date)
        for symbol in target_list
        if symbol in by_symbol and symbol not in terminal_targets
    ]
    return {
        "rows": normalized,
        "target_count": len(target_list),
        "response_count": len(normalized),
        "missing_symbols": missing,
        "unverified_no_krx": allowed_missing,
        "terminal_excluded_symbols": sorted(terminal_targets),
        "terminal_symbols_present_in_response": sorted(terminal_targets & response_set),
        "duplicate_symbols": duplicates,
        "extra_symbols": extras,
        "zero_volume_symbols": sorted(row["symbol"] for row in normalized if row["zero_volume"]),
    }


def build_fundamentals(
    rows: Iterable[dict],
    capture_root: Path,
    trade_date: date,
) -> tuple[list[dict], dict[str, list[str]]]:
    fundamentals = []
    warnings: dict[str, list[str]] = {}
    for price in rows:
        snapshot = load_snapshot(capture_root, trade_date, price["symbol"])
        row, row_warnings = normalize_staged_fundamentals(snapshot, price)
        row["market_cap"] = price["market_cap"]
        row["listed_shares"] = price["listed_shares"]
        ratios = analysis_ratios(row)
        row.update({
            key: value.quantize(Decimal("0.000001")) if value is not None else None
            for key, value in ratios.items()
        })
        fundamentals.append(row)
        warnings[price["symbol"]] = row_warnings
    return fundamentals, warnings


def _plain_price(row: dict) -> dict:
    return {key: value for key, value in row.items() if key not in {"raw", "zero_volume"}}


PRICE_COLUMNS = (
    "symbol", "trade_date", "open", "high", "low", "close", "volume",
    "trade_value", "market_cap", "listed_shares", "source", "market_metadata_source",
)
FUNDAMENTAL_COLUMNS = (
    "symbol", "basis_trade_date", "per", "pbr", "eps", "bps", "w52_high",
    "w52_high_date", "w52_low", "w52_low_date", "market_cap", "listed_shares",
    "reference_price", "final_close", "source", "collected_at", "analysis_per", "analysis_pbr",
)
ADJUSTED_COLUMNS = (
    "symbol", "trade_date", "open", "high", "low", "close", "volume", "source", "adjustment_basis",
)


def assert_friday_schema(*, engine=None) -> None:
    db = engine or get_engine()
    required = {
        "prices_daily": set(PRICE_COLUMNS),
        "adjusted_prices_daily": set(ADJUSTED_COLUMNS) | {"collected_at"},
        "stock_fundamentals_snapshot": set(FUNDAMENTAL_COLUMNS),
    }
    with db.connect() as connection:
        rows = connection.execute(text("""
            SELECT table_name, column_name FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name IN ('prices_daily','adjusted_prices_daily','stock_fundamentals_snapshot')
        """))
        present: dict[str, set[str]] = {}
        for table_name, column_name in rows:
            present.setdefault(table_name, set()).add(column_name)
    missing = {table: sorted(columns - present.get(table, set())) for table, columns in required.items()
               if columns - present.get(table, set())}
    if missing:
        raise FridayInputError("금요일 파이프라인 DB 스키마가 준비되지 않았습니다: " + json.dumps(missing))


def _row_equal(actual: dict, expected: dict, columns: Iterable[str]) -> bool:
    for key in columns:
        left, right = actual.get(key), expected.get(key)
        if isinstance(left, Decimal) or isinstance(right, Decimal):
            try:
                if left is None or right is None:
                    if left is not right:
                        return False
                elif Decimal(str(left)) != Decimal(str(right)):
                    return False
            except InvalidOperation:
                return False
        elif left != right:
            return False
    return True


def save_raw_bundle(raw_rows: list[dict], fundamentals: list[dict], *, engine=None) -> dict:
    """Insert a complete Saturday bundle without updating any existing row."""

    if not raw_rows or len(raw_rows) != len(fundamentals):
        raise FridayInputError("토요일 원시 가격과 투자지표 건수가 다릅니다.")
    db = engine or get_engine()
    trade_dates = {row["trade_date"] for row in raw_rows}
    if len(trade_dates) != 1:
        raise FridayInputError("토요일 저장 묶음은 한 거래일이어야 합니다.")
    trade_date = next(iter(trade_dates))
    symbols = tuple(row["symbol"] for row in raw_rows)
    raw_values = [_plain_price(row) for row in raw_rows]
    price_insert = text("""
        INSERT INTO prices_daily (
          symbol, trade_date, open, high, low, close, volume, trade_value,
          market_cap, listed_shares, source, market_metadata_source
        ) VALUES (
          :symbol, :trade_date, :open, :high, :low, :close, :volume, :trade_value,
          :market_cap, :listed_shares, :source, :market_metadata_source
        ) ON CONFLICT (symbol, trade_date) DO NOTHING
    """)
    fundamental_insert = text("""
        INSERT INTO stock_fundamentals_snapshot (
          symbol, basis_trade_date, per, pbr, eps, bps, w52_high, w52_high_date,
          w52_low, w52_low_date, market_cap, listed_shares, reference_price,
          final_close, source, collected_at, analysis_per, analysis_pbr
        ) VALUES (
          :symbol, :basis_trade_date, :per, :pbr, :eps, :bps, :w52_high, :w52_high_date,
          :w52_low, :w52_low_date, :market_cap, :listed_shares, :reference_price,
          :final_close, :source, :collected_at, :analysis_per, :analysis_pbr
        ) ON CONFLICT (symbol, basis_trade_date) DO NOTHING
    """)
    select_prices = text("SELECT * FROM prices_daily WHERE trade_date=:day AND symbol IN :symbols").bindparams(
        bindparam("symbols", expanding=True)
    )
    select_fundamentals = text(
        "SELECT * FROM stock_fundamentals_snapshot WHERE basis_trade_date=:day AND symbol IN :symbols"
    ).bindparams(bindparam("symbols", expanding=True))
    with db.begin() as connection:
        current_prices = {str(row["symbol"]).strip(): dict(row) for row in connection.execute(
            select_prices, {"day": trade_date, "symbols": symbols}
        ).mappings()}
        current_fundamentals = {str(row["symbol"]).strip(): dict(row) for row in connection.execute(
            select_fundamentals, {"day": trade_date, "symbols": symbols}
        ).mappings()}
        for expected in raw_values:
            actual = current_prices.get(expected["symbol"])
            if actual is not None and not _row_equal(actual, expected, PRICE_COLUMNS):
                raise FridayConflictError(f"기존 원시 가격과 충돌합니다: {expected['symbol']}")
        for expected in fundamentals:
            actual = current_fundamentals.get(expected["symbol"])
            if actual is not None and not _row_equal(actual, expected, FUNDAMENTAL_COLUMNS):
                raise FridayConflictError(f"기존 투자지표와 충돌합니다: {expected['symbol']}")
        missing_prices = [row for row in raw_values if row["symbol"] not in current_prices]
        missing_fundamentals = [row for row in fundamentals if row["symbol"] not in current_fundamentals]
        if missing_prices:
            connection.execute(price_insert, missing_prices)
        if missing_fundamentals:
            connection.execute(fundamental_insert, missing_fundamentals)
        saved_prices = {str(row["symbol"]).strip(): dict(row) for row in connection.execute(
            select_prices, {"day": trade_date, "symbols": symbols}
        ).mappings()}
        saved_fundamentals = {str(row["symbol"]).strip(): dict(row) for row in connection.execute(
            select_fundamentals, {"day": trade_date, "symbols": symbols}
        ).mappings()}
        if any(
            not _row_equal(saved_prices.get(row["symbol"], {}), row, PRICE_COLUMNS)
            for row in raw_values
        ):
            raise FridayConflictError("토요일 원시 가격 저장 후 검증에 실패했습니다.")
        if any(
            not _row_equal(saved_fundamentals.get(row["symbol"], {}), row, FUNDAMENTAL_COLUMNS)
            for row in fundamentals
        ):
            raise FridayConflictError("토요일 투자지표 저장 후 검증에 실패했습니다.")
    return {
        "raw_inserted": len(missing_prices),
        "raw_existing": len(raw_values) - len(missing_prices),
        "fundamentals_inserted": len(missing_fundamentals),
        "fundamentals_existing": len(fundamentals) - len(missing_fundamentals),
    }


def load_db_stage_state(trade_date: date, symbols: Iterable[str], *, engine=None) -> dict:
    values = tuple(symbols)
    if not values:
        return {"raw_symbols": set(), "fundamental_symbols": set(), "adjusted_symbols": set()}
    db = engine or get_engine()
    queries = {
        "raw_symbols": "SELECT symbol FROM prices_daily WHERE trade_date=:day AND source='KRX_OPEN_API' AND symbol IN :symbols",
        "fundamental_symbols": "SELECT symbol FROM stock_fundamentals_snapshot WHERE basis_trade_date=:day AND symbol IN :symbols",
        "adjusted_symbols": """SELECT symbol FROM adjusted_prices_daily
                               WHERE trade_date=:day AND source='KIS'
                                 AND adjustment_basis='KIS_FID_ORG_ADJ_PRC_0_V1'
                                 AND symbol IN :symbols""",
    }
    result = {}
    with db.connect() as connection:
        for key, sql in queries.items():
            statement = text(sql).bindparams(bindparam("symbols", expanding=True))
            result[key] = {str(value).strip() for value in connection.execute(
                statement, {"day": trade_date, "symbols": values}
            ).scalars()}
    return result


def save_adjusted_row(row: dict, *, engine=None) -> str:
    db = engine or get_engine()
    select_row = text("SELECT * FROM adjusted_prices_daily WHERE symbol=:symbol AND trade_date=:trade_date")
    insert_row = text("""
        INSERT INTO adjusted_prices_daily (
          symbol, trade_date, open, high, low, close, volume, source, adjustment_basis, collected_at
        ) VALUES (
          :symbol, :trade_date, :open, :high, :low, :close, :volume, :source, :adjustment_basis, :collected_at
        ) ON CONFLICT (symbol, trade_date) DO NOTHING
    """)
    with db.begin() as connection:
        actual_row = connection.execute(select_row, row).mappings().first()
        if actual_row is not None:
            actual = dict(actual_row)
            if not _row_equal(actual, row, ADJUSTED_COLUMNS):
                raise FridayConflictError(f"기존 수정주가와 충돌합니다: {row['symbol']}")
            return "existing"
        connection.execute(insert_row, row)
        saved = connection.execute(select_row, row).mappings().first()
        if saved is None or not _row_equal(dict(saved), row, ADJUSTED_COLUMNS):
            raise FridayConflictError(f"수정주가 저장 후 검증에 실패했습니다: {row['symbol']}")
    return "inserted"


def _restore_adjusted_row(row: dict) -> dict:
    restored = dict(row)
    restored["trade_date"] = date.fromisoformat(str(restored["trade_date"]))
    for key in ("open", "high", "low", "close"):
        restored[key] = Decimal(str(restored[key]))
    restored["volume"] = int(restored["volume"])
    restored["collected_at"] = datetime.fromisoformat(str(restored["collected_at"]))
    return restored


def run_saturday(
    trade_date: date,
    *,
    capture_root: Path = RAW_SNAPSHOT_ROOT,
    state_root: Path = STATE_ROOT,
    fetcher: Callable[[date], KrxDailySnapshot] = fetch_kospi_daily_snapshot,
    saver: Callable[[list[dict], list[dict]], dict] = save_raw_bundle,
    statuses: dict[str, SymbolStatus] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict:
    root = state_root / trade_date.isoformat()
    summary_path = root / "saturday_summary.json"
    if summary_path.is_file():
        existing = _read_json(summary_path)
        if existing.get("status") == RAW_READY:
            _load_saturday(root, trade_date)
            stored_capture = _read_json(root / "capture_evidence.json")
            current_capture = capture_evidence(capture_root, trade_date)
            if (
                stored_capture.get("summary_sha256") != current_capture.get("summary_sha256")
                or stored_capture.get("target_symbols") != current_capture.get("target_symbols")
            ):
                raise FridayConflictError("완료 후 Capture 입력이 변경됐습니다.")
            return {**existing, "already_complete": True}
    started = now()
    result = {
        "schema_version": SCHEMA_VERSION,
        "stage": "saturday_krx_raw",
        "trade_date": trade_date.isoformat(),
        "status": RETRY_REQUIRED,
        "started_at": _iso(started),
    }
    try:
        capture = capture_evidence(capture_root, trade_date)
        targets = tuple(capture["target_symbols"])
        registry = statuses if statuses is not None else load_symbol_statuses()
        raw_path = root / "krx_raw_response.json"
        if raw_path.is_file():
            raw_content = raw_path.read_bytes()
            payload = json.loads(raw_content)
            raw_rows = payload.get("OutBlock_1")
            if not isinstance(raw_rows, list):
                raise FridayInputError("보존된 KRX 원본 형식이 올바르지 않습니다.")
            request = {"reused_preserved_raw": True, "http_requests": 0}
        else:
            response = fetcher(trade_date)
            if response.trade_date != trade_date or response.status_code != 200:
                raise FridayInputError("KRX 응답 거래일 또는 HTTP 상태가 올바르지 않습니다.")
            raw_content = response.raw_content
            try:
                parsed_raw = json.loads(raw_content)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise FridayInputError("KRX 원본 응답이 유효한 JSON이 아닙니다.") from exc
            if parsed_raw.get("OutBlock_1") != response.rows:
                raise FridayInputError("KRX 원본 응답과 파싱 행이 일치하지 않습니다.")
            _write_once(raw_path, raw_content)
            raw_rows = response.rows
            request = {
                "reused_preserved_raw": False,
                "http_requests": 1,
                "status": response.status_code,
                "content_type": response.content_type,
            }
        validated = validate_krx_rows(raw_rows, targets, trade_date, registry)
        normalized_path = root / "krx_normalized.json"
        normalized_payload = json.dumps(
            {"trade_date": trade_date.isoformat(), "rows": validated["rows"]},
            ensure_ascii=False,
            indent=2,
            default=str,
        ).encode()
        _write_once(normalized_path, normalized_payload)
        fundamentals, warnings = build_fundamentals(validated["rows"], capture_root, trade_date)
        db = saver(validated["rows"], fundamentals)
        capture_path = root / "capture_evidence.json"
        _write_once(capture_path, json.dumps(capture, ensure_ascii=False, indent=2).encode())
        entries = _write_manifest(root, (
            "capture_evidence.json", "krx_raw_response.json", "krx_normalized.json"
        ))
        result.update(
            status=RAW_READY,
            finished_at=_iso(now()),
            capture={key: value for key, value in capture.items() if key != "target_symbols"},
            request=request,
            raw_sha256=entries["krx_raw_response.json"],
            validation={key: value for key, value in validated.items() if key != "rows"},
            fundamentals_count=len(fundamentals),
            fundamentals_warning_symbols=sorted(symbol for symbol, value in warnings.items() if value),
            db=db,
        )
    except Exception as exc:
        result.update(
            status=RETRY_REQUIRED,
            finished_at=_iso(now()),
            error_type=type(exc).__name__,
            error=str(exc)[:500],
        )
    _atomic_json(summary_path, result)
    return result


def _load_saturday(root: Path, trade_date: date) -> tuple[dict, list[dict]]:
    summary = _read_json(root / "saturday_summary.json")
    if summary.get("status") != RAW_READY or summary.get("trade_date") != trade_date.isoformat():
        raise FridayInputError("토요일 원시 단계가 완료되지 않았습니다.")
    entries = verify_manifest(root, ("capture_evidence.json", "krx_raw_response.json", "krx_normalized.json"))
    if entries["krx_raw_response.json"] != summary.get("raw_sha256"):
        raise FridayInputError("토요일 원본 SHA-256 기록이 다릅니다.")
    normalized = _read_json(root / "krx_normalized.json")
    rows = normalized.get("rows")
    if not isinstance(rows, list):
        raise FridayInputError("토요일 정규화 KRX 행이 없습니다.")
    return summary, rows


def run_monday(
    trade_date: date,
    *,
    client,
    state_root: Path = STATE_ROOT,
    db_state_loader: Callable[[date, Iterable[str]], dict] = load_db_stage_state,
    adjusted_saver: Callable[[dict], str] = save_adjusted_row,
    deadline: datetime,
    request_cap: int | None = None,
    delayed_recovery: bool = False,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict:
    root = state_root / trade_date.isoformat()
    summary_path = root / "monday_summary.json"
    if summary_path.is_file():
        existing_summary = _read_json(summary_path)
        if existing_summary.get("status") == ADJUSTED_FINALIZED:
            progress = _read_json(root / "monday_progress.json")
            symbols = sorted((progress.get("symbols") or {}).keys())
            verify_manifest(root, (
                "capture_evidence.json", "krx_raw_response.json", "krx_normalized.json",
                "monday_progress.json", "monday_summary.json",
                *(f"kis/{symbol}.json" for symbol in symbols),
            ))
            db_state = db_state_loader(trade_date, symbols)
            expected = set(symbols)
            for key in ("raw_symbols", "fundamental_symbols", "adjusted_symbols"):
                if set(db_state.get(key) or ()) != expected:
                    raise FridayConflictError(f"완료 마커와 DB {key} 집합이 다릅니다.")
            for symbol in symbols:
                observation = _read_json(root / "kis" / f"{symbol}.json")
                adjusted_saver(_restore_adjusted_row(observation["adjusted"]))
            return {**existing_summary, "already_complete": True}
    started = now()
    result = {
        "schema_version": SCHEMA_VERSION,
        "stage": "monday_kis_adjusted",
        "trade_date": trade_date.isoformat(),
        "status": RETRY_REQUIRED,
        "started_at": _iso(started),
        "deadline": _iso(deadline),
        "request_cap": request_cap,
        "delayed_recovery": delayed_recovery,
        "completed_symbols": [],
        "failed_symbols": [],
        "errors": {},
        "comparisons": {},
    }
    progress_path = root / "monday_progress.json"
    try:
        saturday, krx_rows = _load_saturday(root, trade_date)
        by_symbol = {row["symbol"]: row for row in krx_rows}
        expected = tuple(sorted(by_symbol))
        db_state = db_state_loader(trade_date, expected)
        if set(expected) != set(db_state.get("raw_symbols") or ()):
            raise FridayInputError("DB의 토요일 KRX 원시 가격 집합이 완료 상태와 다릅니다.")
        if set(expected) != set(db_state.get("fundamental_symbols") or ()):
            raise FridayInputError("DB의 토요일 투자지표 집합이 완료 상태와 다릅니다.")
        progress = _read_json(progress_path) if progress_path.is_file() else {
            "trade_date": trade_date.isoformat(), "symbols": {}
        }
        if progress.get("trade_date") != trade_date.isoformat():
            raise FridayInputError("월요일 재개 체크포인트 거래일이 다릅니다.")
        completed = set()
        consecutive_limit_errors = 0
        for symbol in expected:
            saved = (progress.get("symbols") or {}).get(symbol) or {}
            observation_path = root / "kis" / f"{symbol}.json"
            if saved.get("status") == "complete" and observation_path.is_file():
                if saved.get("sha256") != _sha256(observation_path):
                    raise FridayInputError(f"월요일 종목 원본 SHA-256 불일치: {symbol}")
                observation = _read_json(observation_path)
                adjusted = observation.get("adjusted")
                if not isinstance(adjusted, dict):
                    raise FridayInputError(f"월요일 보존 수정행 형식 오류: {symbol}")
                adjusted = _restore_adjusted_row(adjusted)
                # The strict saver is also the DB equality check.  It returns
                # "existing" for an identical row and raises on any conflict.
                adjusted_saver(adjusted)
                completed.add(symbol)
                result["comparisons"][symbol] = observation["comparison"]
                continue
            if now() >= deadline:
                result["errors"][symbol] = "deadline"
                break
            try:
                raw_rows, raw_zero = fetch_daily_range(
                    client, symbol, trade_date, trade_date, adjusted=False
                )
                adjusted_rows, adjusted_zero = fetch_daily_range(
                    client, symbol, trade_date, trade_date, adjusted=True
                )
                if raw_zero or adjusted_zero or len(raw_rows) != 1 or len(adjusted_rows) != 1:
                    raise FridayInputError("KIS 원시·수정 일봉을 각각 한 건 확보하지 못했습니다.")
                reason = verify_raw_daily_against_krx(
                    raw_rows[0], by_symbol[symbol]["raw"], adjusted_daily=adjusted_rows[0]
                )
                adjusted = dict(adjusted_rows[0])
                adjusted["source"] = KIS_SOURCE
                adjusted["adjustment_basis"] = ADJUSTMENT_BASIS
                save_result = adjusted_saver(adjusted)
                differences = {
                    key: [raw_rows[0][key], adjusted[key]]
                    for key in ("open", "high", "low", "close", "volume")
                    if raw_rows[0][key] != adjusted[key]
                }
                comparison = {
                    "raw_vs_krx": "matched",
                    "representation_reason": reason,
                    "raw_vs_adjusted_differences": differences,
                    "save_result": save_result,
                }
                observation = {
                    "symbol": symbol,
                    "trade_date": trade_date.isoformat(),
                    "raw": raw_rows[0],
                    "adjusted": adjusted,
                    "comparison": comparison,
                    "collected_at": _iso(now()),
                }
                payload = json.dumps(observation, ensure_ascii=False, indent=2, default=str).encode()
                _write_once(observation_path, payload)
                progress["symbols"][symbol] = {
                    "status": "complete", "sha256": hashlib.sha256(payload).hexdigest()
                }
                _atomic_json(progress_path, progress)
                completed.add(symbol)
                result["comparisons"][symbol] = comparison
                consecutive_limit_errors = 0
            except Exception as exc:
                message = f"{type(exc).__name__}: {str(exc)[:300]}"
                result["errors"][symbol] = message
                if any(code in message for code in ("OPSQ0008", "EGW00201", "요청 상한")):
                    consecutive_limit_errors += 1
                    if consecutive_limit_errors >= 5 or "요청 상한" in message:
                        result["stop_reason"] = "consecutive_api_limit_errors"
                        break
                else:
                    consecutive_limit_errors = 0
        failed = sorted(set(expected) - completed)
        result.update(
            completed_symbols=sorted(completed),
            failed_symbols=failed,
            unverified_no_krx=saturday.get("validation", {}).get("unverified_no_krx", []),
            raw_vs_adjusted_diff_symbols=sorted(
                symbol for symbol, comparison in result["comparisons"].items()
                if comparison.get("raw_vs_adjusted_differences")
            ),
            zero_volume_representation_symbols=sorted(
                symbol for symbol, comparison in result["comparisons"].items()
                if comparison.get("representation_reason")
            ),
            finished_at=_iso(now()),
        )
        if not failed and len(completed) == len(expected):
            result["status"] = ADJUSTED_FINALIZED
            final_manifest_names = [
                "capture_evidence.json", "krx_raw_response.json", "krx_normalized.json",
                "monday_progress.json", "monday_summary.json",
                *(f"kis/{symbol}.json" for symbol in expected),
            ]
            result["artifact_count"] = len(final_manifest_names)
        else:
            result["status"] = RETRY_REQUIRED
    except Exception as exc:
        result.update(
            status=RETRY_REQUIRED,
            finished_at=_iso(now()),
            error_type=type(exc).__name__,
            error=str(exc)[:500],
        )
    if hasattr(client, "request_metrics"):
        result["request_metrics"] = client.request_metrics()
    _atomic_json(summary_path, result)
    if result.get("status") == ADJUSTED_FINALIZED:
        _write_manifest(root, final_manifest_names)
    return result
