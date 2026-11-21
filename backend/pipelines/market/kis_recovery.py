"""Bounded recovery helpers for the partial 2026-11-18 KIS outage.

This module is deliberately date/manifest constrained.  Importing it performs
no network or database work; callers must explicitly opt in to execution and
database writes.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text

from pipelines.common.db import get_read_engine
from pipelines.market.kis import fetch_daily_range
from pipelines.market.kis_fundamentals import finalization_path, snapshot_path


TRADE_DATE = date(2026, 11, 18)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = PROJECT_ROOT / "configs/recovery/kis_20261118.json"
DEFAULT_STATE_ROOT = PROJECT_ROOT / "logs/market/kis_fundamentals_raw_v1"
DEFAULT_RECOVERY_ROOT = PROJECT_ROOT / "logs/market/kis_recovery_20261118"
MIN_BATCH_SIZE = 20
MAX_BATCH_SIZE = 25
SEOUL = ZoneInfo("Asia/Seoul")
CONFLICTING_SERVICES = (
    "memos-kis-two-stage-capture.service",
    "memos-kis-two-stage-finalize.service",
    "memos-market-refresh-morning.service",
    "memos-market-refresh-evening.service",
    "memos-adjusted-price-check.service",
)


class RecoverySafetyError(RuntimeError):
    """Raised before work when immutable recovery evidence has drifted."""


class RequestBudgetExceeded(RecoverySafetyError):
    """Raised before an HTTP call would exceed the configured hard limit."""


def symbol_hash(symbols: Iterable[str]) -> str:
    canonical = "".join(f"{symbol}\n" for symbol in sorted(symbols))
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("trade_date") != TRADE_DATE.isoformat():
        raise RecoverySafetyError("복구 manifest 거래일이 2026-11-18이 아닙니다.")
    return payload


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RecoverySafetyError(f"JSON 객체가 아닙니다: {path}")
    return value


def validate_manifest(
    manifest: dict,
    *,
    project_root: Path = PROJECT_ROOT,
    state_root: Path = DEFAULT_STATE_ROOT,
) -> dict:
    """Re-derive 169/132/635 from immutable evidence and compare hashes."""

    finalize_symbols = tuple(manifest["finalize_symbols"])
    price_only_symbols = tuple(manifest["price_only_symbols"])
    if len(finalize_symbols) != 169 or len(price_only_symbols) != 132:
        raise RecoverySafetyError("manifest 대상 수가 169/132와 다릅니다.")
    if set(finalize_symbols) & set(price_only_symbols):
        raise RecoverySafetyError("Finalize와 가격 전용 대상이 겹칩니다.")
    if symbol_hash(finalize_symbols) != manifest["finalize_symbols_sha256"]:
        raise RecoverySafetyError("169종목 SHA-256이 일치하지 않습니다.")
    if symbol_hash(price_only_symbols) != manifest["price_only_symbols_sha256"]:
        raise RecoverySafetyError("132종목 SHA-256이 일치하지 않습니다.")

    capture = _read_json(project_root / manifest["source_capture_summary"])
    finalized = _read_json(project_root / manifest["source_finalize_summary"])
    targets = set(capture.get("target_symbols") or ())
    captured = set(capture.get("captured_symbols") or ())
    failed_capture = set(capture.get("failed_symbols") or ())
    if len(targets) != 936 or captured | failed_capture != targets:
        raise RecoverySafetyError("Capture summary의 936종목 분할이 변경됐습니다.")

    marker_symbols = {
        symbol
        for symbol in targets
        if finalization_path(state_root, TRADE_DATE, symbol).is_file()
    }
    baseline_markers = marker_symbols - set(finalize_symbols)
    if len(baseline_markers) != manifest["expected_completed_count"]:
        raise RecoverySafetyError("기존 완료 집합이 기준 635와 다릅니다.")
    if marker_symbols & set(price_only_symbols):
        raise RecoverySafetyError("가격 전용 대상에 Finalize 완료 마커가 생겼습니다.")
    if baseline_markers | set(finalize_symbols) | set(price_only_symbols) != targets:
        raise RecoverySafetyError("635/169/132 합집합이 고정 대상 936과 다릅니다.")
    if set(finalize_symbols) - captured:
        raise RecoverySafetyError("169종목 중 Capture 성공 기록이 없는 종목이 있습니다.")
    if any(not snapshot_path(state_root, TRADE_DATE, s).is_file() for s in finalize_symbols):
        raise RecoverySafetyError("169종목 중 Capture JSON이 없는 종목이 있습니다.")
    if set(price_only_symbols) != failed_capture:
        raise RecoverySafetyError("132종목이 Capture 실패 집합과 다릅니다.")
    finalize_errors = finalized.get("errors") or {}
    if any("OPSQ0008" not in str(finalize_errors.get(s, {}).get("error", "")) for s in finalize_symbols):
        raise RecoverySafetyError("169종목의 기존 OPSQ0008 근거가 변경됐습니다.")
    return {
        "targets": tuple(sorted(targets)),
        "completed_symbols": tuple(sorted(marker_symbols)),
        "baseline_completed_symbols": tuple(sorted(baseline_markers)),
        "finalize_symbols": finalize_symbols,
        "price_only_symbols": price_only_symbols,
    }


def make_batches(symbols: Iterable[str], batch_size: int = 25) -> list[tuple[str, ...]]:
    if not MIN_BATCH_SIZE <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError("배치 크기는 20~25종목이어야 합니다.")
    values = tuple(symbols)
    if not values:
        return []
    batch_count = (len(values) + batch_size - 1) // batch_size
    base, remainder = divmod(len(values), batch_count)
    if batch_count > 1 and base < MIN_BATCH_SIZE:
        raise ValueError("모든 배치를 20~25종목으로 나눌 수 없습니다.")
    batches = []
    offset = 0
    for index in range(batch_count):
        size = base + (1 if index < remainder else 0)
        batches.append(values[offset:offset + size])
        offset += size
    return batches


def select_batches(
    batches: list[tuple[str, ...]],
    *,
    batch_number: int | None = None,
    max_batches: int | None = None,
) -> list[tuple[int, tuple[str, ...]]]:
    """Return 1-indexed bounded batches; used to authorize limited runs."""

    indexed = list(enumerate(batches, 1))
    if batch_number is not None:
        if batch_number < 1 or batch_number > len(indexed):
            raise ValueError("batch-number가 유효한 배치 범위를 벗어났습니다.")
        indexed = [indexed[batch_number - 1]]
    if max_batches is not None:
        if max_batches < 1:
            raise ValueError("max-batches는 1 이상이어야 합니다.")
        indexed = indexed[:max_batches]
    return indexed


class CappedSession:
    """requests-compatible wrapper counting every quotation GET, including retries."""

    def __init__(self, delegate, max_get_requests: int) -> None:
        if max_get_requests < 1:
            raise ValueError("요청 상한은 1 이상이어야 합니다.")
        self.delegate = delegate
        self.max_get_requests = max_get_requests
        self.get_requests = 0

    def get(self, *args, **kwargs):
        if self.get_requests >= self.max_get_requests:
            raise RequestBudgetExceeded(
                f"KIS 시세 요청 상한 {self.max_get_requests}회를 초과할 수 없습니다."
            )
        self.get_requests += 1
        return self.delegate.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        return self.delegate.post(*args, **kwargs)

    def close(self) -> None:
        self.delegate.close()

    def __getattr__(self, name):
        return getattr(self.delegate, name)


def opsq0008_streak(errors: Iterable[object]) -> int:
    streak = longest = 0
    for error in errors:
        if "OPSQ0008" in str(error):
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 0
    return longest


def should_stop_for_opsq0008(errors: Iterable[object], threshold: int) -> bool:
    if threshold < 1:
        raise ValueError("OPSQ0008 연속 오류 중단 기준은 1 이상이어야 합니다.")
    return opsq0008_streak(errors) >= threshold


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def checkpoint_symbols(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    payload = _read_json(path)
    if payload.get("trade_date") != TRADE_DATE.isoformat():
        raise RecoverySafetyError("체크포인트 거래일이 다릅니다.")
    return set(payload.get("saved_symbols") or ())


def assert_safe_execution_window(
    *,
    now: datetime | None = None,
    active_checker: Callable[[str], bool] | None = None,
) -> None:
    """Yield to regular collectors and their surrounding operating windows."""

    current = (now or datetime.now(SEOUL)).astimezone(SEOUL)
    blocked = (
        time(7, 40) <= current.time() <= time(9, 45)
        or time(14, 15) <= current.time() <= time(15, 0)
        or time(19, 40) <= current.time() <= time(20, 45)
    )
    if blocked:
        raise RecoverySafetyError("정규 수집 보호 시간대에는 복구를 실행하지 않습니다.")
    if active_checker is None:
        def active_checker(unit: str) -> bool:
            completed = subprocess.run(
                ["systemctl", "--user", "is-active", "--quiet", unit],
                check=False,
                capture_output=True,
            )
            return completed.returncode == 0
    active = [unit for unit in CONFLICTING_SERVICES if active_checker(unit)]
    if active:
        raise RecoverySafetyError("실행 중 수집 서비스가 있습니다: " + ", ".join(active))


def assert_allowed(requested: Iterable[str], allowed: Iterable[str]) -> tuple[str, ...]:
    values = tuple(requested)
    unexpected = sorted(set(values) - set(allowed))
    if unexpected:
        raise RecoverySafetyError(
            "허용 목록 밖 종목은 복구할 수 없습니다: " + ", ".join(unexpected)
        )
    return values


def compare_close_volume(raw_row: dict, krx_row: dict) -> dict:
    """Block only close/volume mismatches; report O/H/L differences separately."""

    def number(value: object) -> Decimal:
        return Decimal(str(value or "").replace(",", "").strip())

    close_match = Decimal(str(raw_row["close"])) == number(krx_row.get("TDD_CLSPRC"))
    volume_match = int(raw_row["volume"]) == int(number(krx_row.get("ACC_TRDVOL")))
    ohl_map = {"open": "TDD_OPNPRC", "high": "TDD_HGPRC", "low": "TDD_LWPRC"}
    ohl_mismatches = [
        field
        for field, krx_field in ohl_map.items()
        if Decimal(str(raw_row[field])) != number(krx_row.get(krx_field))
    ]
    return {
        "allowed": close_match and volume_match,
        "close_match": close_match,
        "volume_match": volume_match,
        "ohl_mismatches": ohl_mismatches,
        "zero_volume_ohl_difference_allowed": bool(
            int(raw_row["volume"]) == 0 and ohl_mismatches and close_match
        ),
    }


def existing_price_symbols(symbols: Iterable[str], *, engine=None) -> set[str]:
    """Read-only preflight: either existing raw or adjusted row means skip."""

    values = tuple(symbols)
    if not values:
        return set()
    owns_engine = engine is None
    db = engine or get_read_engine()
    statement = text(
        """
        SELECT symbol FROM prices_daily
        WHERE trade_date = :trade_date AND symbol IN :symbols
        UNION
        SELECT symbol FROM adjusted_prices_daily
        WHERE trade_date = :trade_date AND symbol IN :symbols
        """
    ).bindparams(bindparam("symbols", expanding=True))
    try:
        with db.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            return {str(value) for value in connection.execute(
                statement, {"trade_date": TRADE_DATE, "symbols": values}
            ).scalars()}
    finally:
        if owns_engine:
            db.dispose()


@dataclass
class PriceRecoveryResult:
    saved: list[str]
    skipped_existing: list[str]
    failed: dict[str, str]
    blocked_krx: dict[str, dict]
    comparisons: dict[str, dict]
    errors_in_order: list[str]


def recover_price_batch(
    symbols: Iterable[str],
    *,
    allowed_symbols: Iterable[str],
    client,
    krx_rows: dict[str, dict],
    existing_symbols: Iterable[str] = (),
    saver: Callable[[list[dict], list[dict]], int] | None = None,
    checkpointed_symbols: Iterable[str] = (),
) -> PriceRecoveryResult:
    """Recover price pairs only.  It never creates snapshots or final markers."""

    requested = assert_allowed(symbols, allowed_symbols)
    existing = set(existing_symbols) | set(checkpointed_symbols)
    result = PriceRecoveryResult([], [], {}, {}, {}, [])
    for symbol in requested:
        if symbol in existing:
            result.skipped_existing.append(symbol)
            continue
        try:
            raw, raw_zero = fetch_daily_range(
                client, symbol, TRADE_DATE, TRADE_DATE, adjusted=False
            )
            adjusted, adjusted_zero = fetch_daily_range(
                client, symbol, TRADE_DATE, TRADE_DATE, adjusted=True
            )
            if raw_zero or adjusted_zero or len(raw) != 1 or len(adjusted) != 1:
                raise RecoverySafetyError("원시·수정 일봉을 각각 한 건 확보하지 못했습니다.")
            krx_row = krx_rows.get(symbol)
            if krx_row is None:
                raise RecoverySafetyError("KRX 정규장 비교 행이 없습니다.")
            comparison = compare_close_volume(raw[0], krx_row)
            result.comparisons[symbol] = comparison
            if not comparison["allowed"]:
                result.blocked_krx[symbol] = comparison
                result.errors_in_order.append("")
                continue
            if saver is not None:
                saver(raw, adjusted)
            result.saved.append(symbol)
            result.errors_in_order.append("")
        except Exception as exc:
            message = f"{type(exc).__name__}: {str(exc)[:240]}"
            result.failed[symbol] = message
            result.errors_in_order.append(message)
    return result


def save_metadata_missing_only(
    rows: list[dict],
    *,
    allowed_symbols: Iterable[str],
    saver: Callable[..., dict] | None = None,
) -> dict:
    assert_allowed((row["symbol"] for row in rows), allowed_symbols)
    if any(row.get("trade_date") != TRADE_DATE for row in rows):
        raise RecoverySafetyError("메타데이터 거래일은 2026-11-18만 허용됩니다.")
    if saver is None:
        return {"dry_run": True, "eligible_rows": len(rows)}
    result = saver(rows, missing_only=True)
    return {"dry_run": False, **result}
