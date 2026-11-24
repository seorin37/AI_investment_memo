"""Fail-closed handling for explicitly approved Finalize omissions.

This does not create snapshots or completion markers.  It only lets the
automatic recovery loop recognise a separately approved, price-only terminal
state after checking immutable manifest evidence and the current database.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable

from sqlalchemy import bindparam, text

from pipelines.common.db import get_read_engine
from pipelines.market.kis_fundamentals import finalization_path, snapshot_path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = (
    PROJECT_ROOT / "configs/recovery/kis_finalize_intentional_missing.json"
)


class IntentionalMissingStateError(RuntimeError):
    """Approved omission evidence or its required stored data has drifted."""


def symbol_hash(symbols: Iterable[str]) -> str:
    canonical = "".join(f"{symbol}\n" for symbol in sorted(symbols))
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _project_file(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise IntentionalMissingStateError(
            "의도적 결측 정책이 프로젝트 밖의 파일을 참조합니다."
        ) from exc
    return path


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntentionalMissingStateError(
            f"의도적 결측 근거 JSON을 읽을 수 없습니다: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise IntentionalMissingStateError(f"JSON 객체가 아닙니다: {path}")
    return payload


def _valid_price_row(row: dict) -> bool:
    try:
        open_, high, low, close = (
            Decimal(str(row[name])) for name in ("open", "high", "low", "close")
        )
        volume = int(row["volume"])
    except (KeyError, TypeError, ValueError):
        return False
    if any(not value.is_finite() for value in (open_, high, low, close)):
        return False
    if min(open_, high, low) < 0 or close <= 0 or volume < 0:
        return False
    if high < max(open_, close, low) or low > min(open_, close, high):
        return False
    return bool(str(row.get("source") or "").strip())


def _load_database_state(
    trade_date: date,
    symbols: tuple[str, ...],
    *,
    engine=None,
) -> dict[str, object]:
    read_engine = engine or get_read_engine()
    params = {"trade_date": trade_date, "symbols": list(symbols)}
    price_sql = text(
        """
        SELECT symbol, open, high, low, close, volume, source,
               market_cap, listed_shares, market_metadata_source
        FROM prices_daily
        WHERE trade_date = :trade_date AND symbol IN :symbols
        """
    ).bindparams(bindparam("symbols", expanding=True))
    adjusted_sql = text(
        """
        SELECT symbol, open, high, low, close, volume, source
        FROM adjusted_prices_daily
        WHERE trade_date = :trade_date AND symbol IN :symbols
        """
    ).bindparams(bindparam("symbols", expanding=True))
    fundamentals_sql = text(
        """
        SELECT symbol
        FROM stock_fundamentals_snapshot
        WHERE basis_trade_date = :trade_date AND symbol IN :symbols
        """
    ).bindparams(bindparam("symbols", expanding=True))

    with read_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            if connection.execute(text("SHOW transaction_read_only")).scalar() != "on":
                raise IntentionalMissingStateError("읽기 전용 DB 세션이 아닙니다.")
            raw_rows = {
                row["symbol"].strip(): dict(row)
                for row in connection.execute(price_sql, params).mappings()
            }
            adjusted_rows = {
                row["symbol"].strip(): dict(row)
                for row in connection.execute(adjusted_sql, params).mappings()
            }
            fundamentals = {
                row["symbol"].strip()
                for row in connection.execute(fundamentals_sql, params).mappings()
            }
        finally:
            transaction.rollback()
    return {
        "raw_rows": raw_rows,
        "adjusted_rows": adjusted_rows,
        "fundamental_symbols": fundamentals,
    }


def intentional_missing_symbols(
    trade_date: date,
    capture_symbols: Iterable[str],
    *,
    state_root: Path,
    policy_path: Path = DEFAULT_POLICY_PATH,
    state_loader: Callable[[date, tuple[str, ...]], dict[str, object]] | None = None,
) -> tuple[str, ...]:
    """Return only fully verified, explicitly approved price-only symbols.

    A missing policy means ordinary Finalize behaviour.  A matching but invalid
    policy raises instead of silently suppressing a real failure.
    """

    if not policy_path.is_file():
        return ()
    policy = _read_json(policy_path)
    if policy.get("schema_version") != 1:
        raise IntentionalMissingStateError("지원하지 않는 의도적 결측 정책 버전입니다.")
    entries = policy.get("entries")
    if not isinstance(entries, list):
        raise IntentionalMissingStateError("의도적 결측 entries가 목록이 아닙니다.")
    matches = [entry for entry in entries if entry.get("trade_date") == trade_date.isoformat()]
    if not matches:
        return ()
    if len(matches) != 1:
        raise IntentionalMissingStateError("같은 거래일의 의도적 결측 정책이 중복됐습니다.")
    entry = matches[0]
    if entry.get("status") != "prices_only_complete":
        raise IntentionalMissingStateError("승인되지 않은 의도적 결측 상태입니다.")

    manifest = _read_json(_project_file(str(entry.get("manifest") or "")))
    if manifest.get("trade_date") != trade_date.isoformat():
        raise IntentionalMissingStateError("복구 manifest 거래일이 정책과 다릅니다.")
    field = str(entry.get("symbols_field") or "")
    symbols_value = manifest.get(field)
    if not isinstance(symbols_value, list):
        raise IntentionalMissingStateError("복구 manifest 종목 목록이 없습니다.")
    symbols = tuple(sorted(str(symbol).strip() for symbol in symbols_value))
    expected_hash = str(entry.get("symbols_sha256") or "")
    if manifest.get(f"{field}_sha256") != expected_hash:
        raise IntentionalMissingStateError("정책과 manifest의 SHA-256이 다릅니다.")
    if symbol_hash(symbols) != expected_hash:
        raise IntentionalMissingStateError("의도적 결측 종목 SHA-256이 일치하지 않습니다.")
    capture_set = {str(symbol).strip() for symbol in capture_symbols}
    if not set(symbols) <= capture_set:
        raise IntentionalMissingStateError("의도적 결측 종목이 고정 Capture 대상 밖에 있습니다.")

    unexpected_snapshots = [
        symbol for symbol in symbols if snapshot_path(state_root, trade_date, symbol).is_file()
    ]
    unexpected_markers = [
        symbol for symbol in symbols if finalization_path(state_root, trade_date, symbol).is_file()
    ]
    if unexpected_snapshots or unexpected_markers:
        raise IntentionalMissingStateError(
            "가격 전용 완료 종목에 Capture JSON 또는 Finalize 마커가 생겼습니다."
        )

    loader = state_loader or (lambda day, values: _load_database_state(day, values))
    try:
        database = loader(trade_date, symbols)
    except IntentionalMissingStateError:
        raise
    except Exception as exc:
        raise IntentionalMissingStateError(
            "가격 전용 완료 상태를 DB에서 검증하지 못했습니다."
        ) from exc
    raw_rows = database.get("raw_rows") or {}
    adjusted_rows = database.get("adjusted_rows") or {}
    fundamentals = set(database.get("fundamental_symbols") or ())
    valid_raw = {
        symbol
        for symbol, row in raw_rows.items()
        if _valid_price_row(row)
        and row.get("market_cap") is not None
        and row.get("listed_shares") is not None
        and str(row.get("market_metadata_source") or "").strip()
    }
    valid_adjusted = {
        symbol for symbol, row in adjusted_rows.items() if _valid_price_row(row)
    }
    required = set(symbols)
    if valid_raw != required or valid_adjusted != required or fundamentals & required:
        missing_raw = sorted(required - valid_raw)
        missing_adjusted = sorted(required - valid_adjusted)
        unexpected_fundamentals = sorted(fundamentals & required)
        raise IntentionalMissingStateError(
            "가격 전용 완료 상태가 DB와 일치하지 않습니다: "
            f"raw={missing_raw[:5]}, adjusted={missing_adjusted[:5]}, "
            f"fundamentals={unexpected_fundamentals[:5]}"
        )
    return symbols
