"""Two-stage KIS fundamentals capture and finalization.

The evening capture stores the provider response locally without touching the
database.  A later finalization run fetches the requested session's raw and
adjusted daily bars, combines the confirmed close with the captured response,
and optionally invokes the existing idempotent database savers.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from pipelines.market.kis import (
    PRICE_PATH,
    PRICE_TR_ID,
    REGULAR_MARKET_CLOSE,
    SEOUL,
    SOURCE,
    KisClient,
    fetch_daily_range,
    save_fundamentals,
    save_kis_prices,
)
from pipelines.market.krx import is_valid_stock_symbol
from pipelines.market.calendar import is_krx_trading_day, previous_krx_trading_day
from pipelines.market.symbol_status import SymbolStatus, select_operational_symbols


SCHEMA_VERSION = 1
FINALIZATION_SCHEMA_VERSION = 1
RAW_SNAPSHOT_ROOT = (
    Path(__file__).resolve().parents[3]
    / "logs"
    / "market"
    / "kis_fundamentals_raw_v1"
)


class FundamentalsSnapshotError(RuntimeError):
    """Raised when a staged provider response is absent or unsafe to use."""


def operational_symbols(
    symbols: Iterable[str],
    *,
    trade_date: date,
    observed_krx_symbols: Iterable[str] | None = None,
    statuses: dict[str, SymbolStatus] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Compatibility wrapper around the reviewed operational status registry."""

    selection = select_operational_symbols(
        symbols,
        trade_date,
        observed_krx_symbols=observed_krx_symbols,
        statuses=statuses,
    )
    return selection["symbols"], selection["terminal_symbols"]


def automatic_capture_date(now: datetime) -> date | None:
    """Return today's KRX session after close, or None on a market holiday."""

    local = now.astimezone(SEOUL)
    return local.date() if is_krx_trading_day(local.date()) else None


def automatic_finalize_date(now: datetime) -> date:
    """Return the latest completed KRX session strictly before today."""

    return previous_krx_trading_day(now.astimezone(SEOUL).date())


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    descriptor = os.open(
        temporary,
        os.O_CREAT | os.O_WRONLY | os.O_TRUNC,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        os.chmod(temporary, 0o600)
        temporary.replace(path)
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def snapshot_path(root: Path, trade_date: date, symbol: str) -> Path:
    if not is_valid_stock_symbol(symbol):
        raise ValueError(f"유효하지 않은 종목코드: {symbol}")
    return root / trade_date.isoformat() / f"{symbol}.json"


def finalization_path(root: Path, trade_date: date, symbol: str) -> Path:
    if not is_valid_stock_symbol(symbol):
        raise ValueError(f"유효하지 않은 종목코드: {symbol}")
    return root / trade_date.isoformat() / "finalized" / f"{symbol}.json"


def is_finalized(root: Path, trade_date: date, symbol: str) -> bool:
    """Validate durable evidence that both price and fundamentals UPSERTs ran."""

    path = finalization_path(root, trade_date, symbol)
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    status = payload.get("status", "finalized")
    return bool(
        isinstance(payload, dict)
        and payload.get("schema_version") == FINALIZATION_SCHEMA_VERSION
        and payload.get("source") == SOURCE
        and payload.get("symbol") == symbol
        and payload.get("basis_trade_date") == trade_date.isoformat()
        and status in {"finalized", "terminal_inactive"}
    )


def mark_terminal_inactive(
    root: Path,
    trade_date: date,
    symbol: str,
    status: SymbolStatus,
) -> bool:
    """Write durable no-data completion evidence without touching DB/history."""

    if not status.is_terminal_on(trade_date):
        return False
    path = finalization_path(root, trade_date, symbol)
    if is_finalized(root, trade_date, symbol):
        return False
    _atomic_json(
        path,
        {
            "schema_version": FINALIZATION_SCHEMA_VERSION,
            "source": SOURCE,
            "status": "terminal_inactive",
            "symbol": symbol,
            "basis_trade_date": trade_date.isoformat(),
            "effective_date": (
                status.effective_date.isoformat() if status.effective_date else None
            ),
            "terminal_status": status.status,
            "reason": status.reason,
            "evidence": status.source,
            "finalized_at": datetime.now(timezone.utc).isoformat(),
            "raw_rows": 0,
            "adjusted_rows": 0,
        },
    )
    return True


def symbols_needing_finalization(
    root: Path,
    trade_date: date,
    symbols: Iterable[str],
) -> tuple[str, ...]:
    return tuple(
        symbol
        for symbol in symbols
        if not is_finalized(root, trade_date, symbol)
    )


def capture_target_symbols(root: Path, trade_date: date) -> tuple[str, ...]:
    """Load the exact symbol universe frozen by that date's capture run."""

    path = root / trade_date.isoformat() / "capture_summary.json"
    if not path.exists():
        raise FundamentalsSnapshotError(
            f"Capture 대상 요약 파일이 없습니다: {trade_date.isoformat()}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FundamentalsSnapshotError(
            f"Capture 대상 요약 파일을 읽을 수 없습니다: {trade_date.isoformat()}"
        ) from exc
    if not isinstance(payload, dict):
        raise FundamentalsSnapshotError("Capture 대상 요약이 JSON 객체가 아닙니다.")

    symbols = payload.get("target_symbols")
    if symbols is None:
        # Backward compatibility for already captured dates.
        symbols = [
            *payload.get("captured_symbols", []),
            *payload.get("skipped_symbols", []),
            *payload.get("failed_symbols", []),
        ]
    if not isinstance(symbols, list):
        raise FundamentalsSnapshotError("Capture 대상 종목 목록 형식이 잘못됐습니다.")
    normalized = tuple(str(symbol).strip() for symbol in symbols)
    if (
        not normalized
        or len(set(normalized)) != len(normalized)
        or any(not is_valid_stock_symbol(symbol) for symbol in normalized)
    ):
        raise FundamentalsSnapshotError("Capture 대상 종목 목록이 유효하지 않습니다.")
    if payload.get("target_count") != len(normalized):
        raise FundamentalsSnapshotError("Capture 대상 건수와 종목 목록이 다릅니다.")
    return normalized


def pending_snapshot_dates(
    root: Path,
    cutoff: date,
    *,
    recovery_days: int = 10,
) -> tuple[date, ...]:
    """Find recent captured sessions eligible for safe re-finalization."""

    if recovery_days < 1:
        raise ValueError("복구 조회 기간은 1일 이상이어야 합니다.")
    lower = cutoff - timedelta(days=recovery_days - 1)
    pending: list[date] = []
    if not root.exists():
        return ()
    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            candidate = date.fromisoformat(child.name)
        except ValueError:
            continue
        if not lower <= candidate <= cutoff or not is_krx_trading_day(candidate):
            continue
        if any(is_valid_stock_symbol(path.stem) for path in child.glob("*.json")):
            pending.append(candidate)
    return tuple(sorted(set(pending)))


def _aware_datetime(value: object, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise FundamentalsSnapshotError(f"{field} 형식이 올바르지 않습니다.") from exc
    if parsed.tzinfo is None:
        raise FundamentalsSnapshotError(f"{field}에 시간대가 없습니다.")
    return parsed.astimezone(timezone.utc)


def validate_snapshot(
    payload: object,
    *,
    expected_symbol: str | None = None,
    expected_trade_date: date | None = None,
) -> dict:
    if not isinstance(payload, dict):
        raise FundamentalsSnapshotError("원본 스냅샷이 JSON 객체가 아닙니다.")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise FundamentalsSnapshotError("지원하지 않는 원본 스냅샷 버전입니다.")
    symbol = str(payload.get("symbol") or "")
    if not is_valid_stock_symbol(symbol):
        raise FundamentalsSnapshotError("원본 스냅샷 종목코드가 올바르지 않습니다.")
    if expected_symbol is not None and symbol != expected_symbol:
        raise FundamentalsSnapshotError("파일명과 원본 스냅샷 종목코드가 다릅니다.")
    try:
        basis_trade_date = date.fromisoformat(str(payload.get("basis_trade_date")))
    except ValueError as exc:
        raise FundamentalsSnapshotError("기준 거래일 형식이 올바르지 않습니다.") from exc
    if expected_trade_date is not None and basis_trade_date != expected_trade_date:
        raise FundamentalsSnapshotError("요청 거래일과 원본 스냅샷 거래일이 다릅니다.")
    collected_at = _aware_datetime(payload.get("collected_at"), "수집 시각")
    raw_output = payload.get("raw_output")
    if not isinstance(raw_output, dict):
        raise FundamentalsSnapshotError("KIS 현재가 원본 응답이 객체가 아닙니다.")
    if payload.get("source") != SOURCE:
        raise FundamentalsSnapshotError("원본 스냅샷 공급원이 KIS가 아닙니다.")
    return {
        **payload,
        "symbol": symbol,
        "basis_trade_date": basis_trade_date,
        "collected_at": collected_at,
        "raw_output": {str(key): str(value) for key, value in raw_output.items()},
    }


def load_snapshot(root: Path, trade_date: date, symbol: str) -> dict:
    path = snapshot_path(root, trade_date, symbol)
    if not path.exists():
        raise FundamentalsSnapshotError(f"원본 스냅샷 파일이 없습니다: {symbol}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FundamentalsSnapshotError(
            f"원본 스냅샷 파일을 읽을 수 없습니다: {symbol}"
        ) from exc
    return validate_snapshot(
        payload,
        expected_symbol=symbol,
        expected_trade_date=trade_date,
    )


def _capture_allowed(snapshot_at: datetime, trade_date: date) -> None:
    local = snapshot_at.astimezone(SEOUL)
    if local.date() != trade_date:
        raise ValueError("Evening 원본 수집일과 기준 거래일이 일치해야 합니다.")
    if local.time() < REGULAR_MARKET_CLOSE:
        raise ValueError("KIS 투자지표 원본은 정규장 마감 후에만 수집합니다.")


def capture_snapshots(
    symbols: Iterable[str],
    trade_date: date,
    *,
    client: KisClient | None = None,
    root: Path = RAW_SNAPSHOT_ROOT,
    overwrite: bool = False,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict:
    """Capture one current-price response per symbol without database writes."""

    requested = tuple(symbols)
    started_at = now()
    _capture_allowed(started_at, trade_date)
    result = {
        "trade_date": trade_date.isoformat(),
        "target_count": len(requested),
        "target_symbols": list(requested),
        "captured_symbols": [],
        "skipped_symbols": [],
        "failed_symbols": [],
        "errors": {},
    }
    own_client = client is None
    api = client or KisClient()
    try:
        for symbol in requested:
            path = snapshot_path(root, trade_date, symbol)
            try:
                if path.exists() and not overwrite:
                    load_snapshot(root, trade_date, symbol)
                    result["skipped_symbols"].append(symbol)
                    continue
                raw_output = api.current_price(symbol)
                collected_at = now()
                _capture_allowed(collected_at, trade_date)
                payload = {
                    "schema_version": SCHEMA_VERSION,
                    "source": SOURCE,
                    "endpoint": PRICE_PATH,
                    "tr_id": PRICE_TR_ID,
                    "symbol": symbol,
                    # This is the market snapshot date selected by the caller,
                    # not an EPS/BPS financial statement date supplied by KIS.
                    "basis_trade_date": trade_date.isoformat(),
                    "collected_at": collected_at.isoformat(),
                    "collected_at_kst": collected_at.astimezone(SEOUL).isoformat(),
                    "raw_output": raw_output,
                }
                validate_snapshot(
                    payload,
                    expected_symbol=symbol,
                    expected_trade_date=trade_date,
                )
                _atomic_json(path, payload)
                result["captured_symbols"].append(symbol)
            except Exception as exc:
                result["failed_symbols"].append(symbol)
                result["errors"][symbol] = {
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                }
            _atomic_json(root / trade_date.isoformat() / "capture_summary.json", result)
    finally:
        if own_client:
            api.close()
    return result


def _nullable_decimal(
    raw: dict[str, str],
    key: str,
    warnings: list[str],
) -> Decimal | None:
    value = str(raw.get(key) or "").replace(",", "").strip()
    if value in {"", "-"}:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        warnings.append(f"{key}:invalid_number")
        return None
    if not parsed.is_finite():
        warnings.append(f"{key}:non_finite")
        return None
    return parsed


def _nullable_integer(
    raw: dict[str, str],
    key: str,
    warnings: list[str],
) -> int | None:
    parsed = _nullable_decimal(raw, key, warnings)
    if parsed is None:
        return None
    if parsed != parsed.to_integral_value():
        warnings.append(f"{key}:not_integer")
        return None
    return int(parsed)


def _nullable_date(
    raw: dict[str, str],
    key: str,
    warnings: list[str],
) -> date | None:
    value = str(raw.get(key) or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        warnings.append(f"{key}:invalid_date")
        return None


def _w52_pair(
    raw: dict[str, str],
    price_key: str,
    date_key: str,
    warnings: list[str],
) -> tuple[Decimal | None, date | None]:
    price = _nullable_decimal(raw, price_key, warnings)
    observed_date = _nullable_date(raw, date_key, warnings)
    if price is None and observed_date is None:
        return None, None
    if price is None or observed_date is None or price <= 0:
        warnings.append(f"{price_key}:{date_key}:invalid_pair")
        return None, None
    return price, observed_date


def normalize_staged_fundamentals(
    snapshot: dict,
    final_daily: dict,
) -> tuple[dict, list[str]]:
    """Normalize fields independently and retain valid provider values."""

    staged = validate_snapshot(snapshot)
    symbol = staged["symbol"]
    basis_trade_date = staged["basis_trade_date"]
    if final_daily.get("symbol", symbol) != symbol:
        raise FundamentalsSnapshotError("확정 일봉 종목코드가 원본과 다릅니다.")
    if final_daily.get("trade_date") != basis_trade_date:
        raise FundamentalsSnapshotError("확정 일봉 거래일이 원본 기준일과 다릅니다.")
    final_close = final_daily.get("close")
    if not isinstance(final_close, Decimal):
        try:
            final_close = Decimal(str(final_close))
        except (InvalidOperation, TypeError) as exc:
            raise FundamentalsSnapshotError("확정 종가가 숫자가 아닙니다.") from exc
    if not final_close.is_finite() or final_close <= 0:
        raise FundamentalsSnapshotError("확정 종가는 양수여야 합니다.")

    raw = staged["raw_output"]
    warnings: list[str] = []
    per = _nullable_decimal(raw, "per", warnings)
    pbr = _nullable_decimal(raw, "pbr", warnings)
    eps = _nullable_decimal(raw, "eps", warnings)
    bps = _nullable_decimal(raw, "bps", warnings)
    if per is not None and per < 0:
        warnings.append("per:negative_nullified")
        per = None
    if pbr is not None and pbr < 0:
        warnings.append("pbr:negative_nullified")
        pbr = None

    reference_price = _nullable_decimal(raw, "stck_prpr", warnings)
    if reference_price is not None and reference_price <= 0:
        warnings.append("stck_prpr:nonpositive_nullified")
        reference_price = None
    if reference_price is None:
        warnings.append("stck_prpr:missing_or_invalid")
    elif reference_price != final_close:
        warnings.append("stck_prpr:final_close_mismatch")

    current_volume = _nullable_integer(raw, "acml_vol", warnings)
    if current_volume is not None and current_volume < 0:
        warnings.append("acml_vol:negative_ignored")
        current_volume = None
    final_volume = final_daily.get("volume")
    if (
        current_volume is not None
        and final_volume is not None
        and current_volume != int(final_volume)
    ):
        warnings.append("acml_vol:final_volume_mismatch")

    w52_high, w52_high_date = _w52_pair(
        raw, "w52_hgpr", "w52_hgpr_date", warnings
    )
    w52_low, w52_low_date = _w52_pair(
        raw, "w52_lwpr", "w52_lwpr_date", warnings
    )
    if w52_high is not None and w52_low is not None and w52_high < w52_low:
        warnings.append("w52:high_below_low_nullified")
        w52_high = w52_high_date = w52_low = w52_low_date = None

    market_cap_units = _nullable_decimal(raw, "hts_avls", warnings)
    if market_cap_units is not None and market_cap_units < 0:
        warnings.append("hts_avls:negative_nullified")
        market_cap_units = None
    market_cap = (
        market_cap_units * Decimal("100000000")
        if market_cap_units is not None
        else None
    )
    listed_shares = _nullable_integer(raw, "lstn_stcn", warnings)
    if listed_shares is not None and listed_shares <= 0:
        warnings.append("lstn_stcn:nonpositive_nullified")
        listed_shares = None

    return {
        "symbol": symbol,
        "basis_trade_date": basis_trade_date,
        "per": per,
        "pbr": pbr,
        "eps": eps,
        "bps": bps,
        "w52_high": w52_high,
        "w52_high_date": w52_high_date,
        "w52_low": w52_low,
        "w52_low_date": w52_low_date,
        "market_cap": market_cap,
        "listed_shares": listed_shares,
        "reference_price": reference_price,
        "final_close": final_close,
        "source": SOURCE,
        "collected_at": staged["collected_at"],
    }, sorted(set(warnings))


def analysis_ratios(row: dict) -> dict[str, Decimal | None]:
    """Calculate confirmed-close ratios without changing stored KIS values."""

    final_close = row["final_close"]
    eps = row.get("eps")
    bps = row.get("bps")
    return {
        "analysis_per": final_close / eps if eps is not None and eps > 0 else None,
        "analysis_pbr": final_close / bps if bps is not None and bps > 0 else None,
    }


def verify_raw_daily_against_krx(raw_daily: dict, krx_row: dict) -> None:
    """Require an exact KRX regular-session OHLCV match when requested."""

    field_map = {
        "open": "TDD_OPNPRC",
        "high": "TDD_HGPRC",
        "low": "TDD_LWPRC",
        "close": "TDD_CLSPRC",
    }
    mismatches: list[str] = []
    for local_field, krx_field in field_map.items():
        try:
            official = Decimal(
                str(krx_row.get(krx_field) or "").replace(",", "").strip()
            )
        except InvalidOperation as exc:
            raise FundamentalsSnapshotError(
                f"KRX 공식 {krx_field} 값이 숫자가 아닙니다."
            ) from exc
        if official != raw_daily[local_field]:
            mismatches.append(local_field)
    try:
        official_volume = int(
            str(krx_row.get("ACC_TRDVOL") or "").replace(",", "").strip()
        )
    except ValueError as exc:
        raise FundamentalsSnapshotError(
            "KRX 공식 ACC_TRDVOL 값이 정수가 아닙니다."
        ) from exc
    if official_volume != raw_daily["volume"]:
        mismatches.append("volume")
    expected_date = raw_daily["trade_date"].strftime("%Y%m%d")
    if str(krx_row.get("BAS_DD") or "").strip() != expected_date:
        mismatches.append("trade_date")
    if mismatches:
        raise FundamentalsSnapshotError(
            "KIS 원시 일봉과 KRX 공식 정규장 값이 다릅니다: "
            + ", ".join(sorted(mismatches))
        )


def finalize_snapshots(
    symbols: Iterable[str],
    trade_date: date,
    *,
    client: KisClient | None = None,
    root: Path = RAW_SNAPSHOT_ROOT,
    krx_rows: dict[str, dict] | None = None,
    krx_strict: bool = True,
    krx_lookup_error: str | None = None,
    price_saver: Callable[[list[dict], list[dict]], int] | None = None,
    fundamentals_saver: Callable[[list[dict]], int] | None = None,
) -> dict:
    """Combine staged fundamentals with confirmed bars; savers enable apply mode."""

    if (price_saver is None) != (fundamentals_saver is None):
        raise ValueError("가격과 투자지표 saver는 함께 지정해야 합니다.")
    apply_changes = price_saver is not None
    requested = tuple(symbols)
    result = {
        "trade_date": trade_date.isoformat(),
        "dry_run": not apply_changes,
        "target_count": len(requested),
        "ready_symbols": [],
        "saved_symbols": [],
        "skipped_symbols": [],
        "failed_symbols": [],
        "warnings": {},
        "krx_comparison": {},
        "analysis_ratios": {},
        "records": {},
        "errors": {},
    }
    own_client = client is None
    api = client or KisClient()
    try:
        for symbol in requested:
            try:
                if apply_changes and is_finalized(root, trade_date, symbol):
                    result["skipped_symbols"].append(symbol)
                    continue
                # Validate the local evidence before making any external call.
                snapshot = load_snapshot(root, trade_date, symbol)
                raw_rows, raw_zero = fetch_daily_range(
                    api, symbol, trade_date, trade_date, adjusted=False
                )
                adjusted_rows, adjusted_zero = fetch_daily_range(
                    api, symbol, trade_date, trade_date, adjusted=True
                )
                if raw_zero or adjusted_zero or len(raw_rows) != 1 or len(adjusted_rows) != 1:
                    raise FundamentalsSnapshotError(
                        "확정 원시·수정 일봉을 각각 한 건 확보하지 못했습니다."
                    )
                krx_warnings: list[str] = []
                if krx_rows is not None:
                    krx_row = krx_rows.get(symbol)
                    if krx_lookup_error is not None:
                        comparison = {
                            "status": "unavailable",
                            "error": krx_lookup_error,
                        }
                    elif krx_row is None:
                        comparison = {
                            "status": "missing",
                            "error": "KRX 공식 정규장 응답에 종목이 없습니다.",
                        }
                    else:
                        try:
                            verify_raw_daily_against_krx(raw_rows[0], krx_row)
                            comparison = {"status": "matched"}
                        except FundamentalsSnapshotError as exc:
                            comparison = {
                                "status": "mismatched",
                                "error": str(exc),
                            }
                    result["krx_comparison"][symbol] = comparison
                    if comparison["status"] != "matched":
                        if krx_strict:
                            raise FundamentalsSnapshotError(comparison["error"])
                        krx_warnings.append(
                            f"krx:{comparison['status']}:{comparison['error']}"
                        )
                row, warnings = normalize_staged_fundamentals(snapshot, raw_rows[0])
                warnings = sorted(set([*warnings, *krx_warnings]))
                result["ready_symbols"].append(symbol)
                result["warnings"][symbol] = warnings
                result["analysis_ratios"][symbol] = analysis_ratios(row)
                result["records"][symbol] = {
                    "raw_ohlcv": {
                        key: raw_rows[0].get(key)
                        for key in (
                            "trade_date", "open", "high", "low", "close", "volume"
                        )
                    },
                    "adjusted_ohlcv": {
                        key: adjusted_rows[0].get(key)
                        for key in (
                            "trade_date", "open", "high", "low", "close", "volume"
                        )
                    },
                    "fundamentals": {
                        key: row.get(key)
                        for key in (
                            "eps", "bps", "per", "pbr", "reference_price",
                            "final_close", "collected_at",
                        )
                    },
                    **result["analysis_ratios"][symbol],
                }
                if apply_changes:
                    assert price_saver is not None and fundamentals_saver is not None
                    price_saver(raw_rows, adjusted_rows)
                    fundamentals_saver([row])
                    result["saved_symbols"].append(symbol)
                    _atomic_json(
                        finalization_path(root, trade_date, symbol),
                        {
                            "schema_version": FINALIZATION_SCHEMA_VERSION,
                            "source": SOURCE,
                            "symbol": symbol,
                            "basis_trade_date": trade_date.isoformat(),
                            "status": "finalized",
                            "finalized_at": datetime.now(timezone.utc).isoformat(),
                            "raw_rows": len(raw_rows),
                            "adjusted_rows": len(adjusted_rows),
                        },
                    )
            except Exception as exc:
                result["failed_symbols"].append(symbol)
                result["errors"][symbol] = {
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                }
            _atomic_json(root / trade_date.isoformat() / "finalize_summary.json", result)
    finally:
        if own_client:
            api.close()
    return result


def apply_savers() -> tuple[
    Callable[[list[dict], list[dict]], int],
    Callable[[list[dict]], int],
]:
    """Return existing UPSERT functions only after explicit CLI opt-in."""

    return save_kis_prices, save_fundamentals
