"""Operational KIS universe state without changing the historical stock schema."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from pipelines.market.krx import is_valid_stock_symbol


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STATUS_PATH = PROJECT_ROOT / "configs" / "kis_symbol_status.json"
STATUS_SCHEMA_VERSION = 1
TERMINAL_STATUSES = frozenset({"delisted", "converted", "terminal_inactive"})


@dataclass(frozen=True)
class SymbolStatus:
    symbol: str
    status: str
    effective_date: date | None
    reason: str
    source: str

    def is_terminal_on(self, trade_date: date) -> bool:
        return self.status in TERMINAL_STATUSES and (
            self.effective_date is None or self.effective_date <= trade_date
        )


def load_symbol_statuses(path: Path = DEFAULT_STATUS_PATH) -> dict[str, SymbolStatus]:
    """Load reviewed operational statuses kept separately from historical rows."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"KIS 종목 상태 파일을 읽을 수 없습니다: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != STATUS_SCHEMA_VERSION:
        raise ValueError("지원하지 않는 KIS 종목 상태 파일입니다.")
    rows = payload.get("symbols")
    if not isinstance(rows, list):
        raise ValueError("KIS 종목 상태 목록 형식이 올바르지 않습니다.")

    result: dict[str, SymbolStatus] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("KIS 종목 상태 항목이 JSON 객체가 아닙니다.")
        symbol = str(row.get("symbol") or "").strip()
        status = str(row.get("status") or "").strip()
        reason = str(row.get("reason") or "").strip()
        source = str(row.get("source") or "").strip()
        raw_effective = row.get("effective_date")
        if not is_valid_stock_symbol(symbol) or symbol in result:
            raise ValueError(f"KIS 종목 상태 코드가 유효하지 않거나 중복됐습니다: {symbol}")
        if status not in TERMINAL_STATUSES or not reason or not source:
            raise ValueError(f"KIS 종목 종료 상태가 올바르지 않습니다: {symbol}")
        try:
            effective_date = (
                None if raw_effective in (None, "") else date.fromisoformat(str(raw_effective))
            )
        except ValueError as exc:
            raise ValueError(f"KIS 종목 상태 효력일이 올바르지 않습니다: {symbol}") from exc
        result[symbol] = SymbolStatus(
            symbol=symbol,
            status=status,
            effective_date=effective_date,
            reason=reason,
            source=source,
        )
    return result


def select_operational_symbols(
    db_symbols: Iterable[str],
    trade_date: date,
    *,
    observed_krx_symbols: Iterable[str] | None = None,
    statuses: dict[str, SymbolStatus] | None = None,
) -> dict:
    """Select active DB symbols while treating one KRX absence as non-terminal.

    The DB remains the durable identity/FK source.  A complete current KRX
    snapshot confirms active listings and detects master-sync lag, but absence
    alone never removes historical DB rows from operation.  Only a reviewed
    terminal status does that.
    """

    db = tuple(str(value).strip() for value in db_symbols)
    if not db or len(set(db)) != len(db) or any(not is_valid_stock_symbol(s) for s in db):
        raise ValueError("DB KOSPI 종목 목록이 비어 있거나 유효하지 않습니다.")
    registry = statuses if statuses is not None else load_symbol_statuses()
    db_set = set(db)
    terminal = {
        symbol: status
        for symbol, status in registry.items()
        if symbol in db_set and status.is_terminal_on(trade_date)
    }
    selected = tuple(sorted(symbol for symbol in db if symbol not in terminal))
    if not selected:
        raise ValueError("자동 KIS 수집 대상이 0종목입니다.")

    observed: set[str] | None = None
    if observed_krx_symbols is not None:
        observed_values = tuple(str(value).strip() for value in observed_krx_symbols)
        if (
            not observed_values
            or len(set(observed_values)) != len(observed_values)
            or any(not is_valid_stock_symbol(s) for s in observed_values)
        ):
            raise ValueError("KRX 최신 종목 목록이 비어 있거나 유효하지 않습니다.")
        observed = set(observed_values)

    selected_set = set(selected)
    return {
        "db_count": len(db),
        "target_count": len(selected),
        "symbols": selected,
        "terminal_symbols": tuple(sorted(terminal)),
        "terminal_statuses": terminal,
        # A one-day absence is diagnostic only and does not deactivate a code.
        "temporarily_absent_symbols": (
            tuple(sorted(selected_set - observed)) if observed is not None else ()
        ),
        # Morning master sync must insert these before KIS DB writes can use them.
        "pending_master_sync_symbols": (
            tuple(sorted(observed - db_set)) if observed is not None else ()
        ),
        "krx_observed_count": len(observed) if observed is not None else None,
    }
