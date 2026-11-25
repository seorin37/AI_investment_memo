#!/usr/bin/env python3
"""Plan or replay the preserved 2026-11-20/23 market artifacts.

The command performs no network requests.  Plan mode uses READONLY_DATABASE_URL.
Writes require --apply, are restricted to the migrated memos server, use INSERT
only, and abort the date transaction before inserting if any existing row
conflicts with the preserved artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

from sqlalchemy import bindparam, create_engine, inspect, text

from pipelines.common.db import load_env
from pipelines.market.friday import build_fundamentals, validate_krx_rows
from pipelines.market.kis import ADJUSTMENT_BASIS, SOURCE as KIS_SOURCE
from pipelines.market.kis_fundamentals import normalize_staged_fundamentals
from pipelines.market.symbol_status import load_symbol_statuses


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = PROJECT_ROOT / "logs/market/kis_fundamentals_raw_v1"
FRIDAY_ROOT = PROJECT_ROOT / "logs/diagnostics/friday_market_final_experiment/20261120"
FRIDAY_KIS_ROOT = PROJECT_ROOT / "logs/diagnostics/friday_market_final_experiment/20261123"
ALLOWED_DATES = (date(2026, 11, 20), date(2026, 11, 23))
EXPECTED_HOST = "220.121.144.76"
EXPECTED_PORT = 25432
EXPECTED_DATABASE = "memos"
FORBIDDEN_TARGET = ("192.168.0.105", 15432)

PRICE_COLUMNS = (
    "symbol", "trade_date", "open", "high", "low", "close", "volume",
    "trade_value", "market_cap", "listed_shares", "source",
    "market_metadata_source",
)
ADJUSTED_COLUMNS = (
    "symbol", "trade_date", "open", "high", "low", "close", "volume",
    "source", "adjustment_basis", "collected_at",
)
FUNDAMENTAL_COLUMNS_0023 = (
    "symbol", "basis_trade_date", "per", "pbr", "eps", "bps", "w52_high",
    "w52_high_date", "w52_low", "w52_low_date", "market_cap",
    "listed_shares", "reference_price", "final_close", "source", "collected_at",
)


class RecoveryError(RuntimeError):
    pass


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RecoveryError(f"JSON object required: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(root: Path) -> None:
    manifest = root / "SHA256SUMS"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split(maxsplit=1)
        path = root / relative.strip()
        if not path.is_file() or _sha256(path) != digest:
            raise RecoveryError(f"SHA256 mismatch: {path}")


def verify_monday_evidence() -> dict:
    root = CAPTURE_ROOT / "2026-11-23"
    capture = _read_json(root / "capture_summary.json")
    finalized = _read_json(root / "finalize_summary.json")
    expected = tuple(capture.get("target_symbols") or ())
    if (
        len(expected) != 935
        or tuple(capture.get("captured_symbols") or ()) != expected
        or tuple(finalized.get("saved_symbols") or ()) != expected
        or finalized.get("failed_symbols")
        or set(finalized.get("records") or {}) != set(expected)
    ):
        raise RecoveryError("2026-11-23 Capture/Finalize evidence is incomplete")
    markers = root / "finalized"
    if any(not (markers / f"{symbol}.json").is_file() for symbol in expected):
        raise RecoveryError("2026-11-23 finalization marker is missing")
    return {"capture": capture, "finalized": finalized, "symbols": expected}


def _decimal(value: object | None) -> Decimal | None:
    if value is None or str(value).strip() in {"", "-"}:
        return None
    return Decimal(str(value).replace(",", "").strip())


def _friday_rows() -> tuple[list[dict], list[dict], list[dict]]:
    verify_manifest(FRIDAY_ROOT)
    verify_manifest(FRIDAY_KIS_ROOT)
    capture = _read_json(CAPTURE_ROOT / "2026-11-20/capture_summary.json")
    targets = tuple(capture.get("target_symbols") or ())
    if len(targets) != 936 or set(capture.get("captured_symbols") or ()) != set(targets):
        raise RecoveryError("2026-11-20 Capture evidence is incomplete")
    raw_payload = _read_json(FRIDAY_ROOT / "krx_raw_response_attempt1.json")
    validated = validate_krx_rows(
        raw_payload.get("OutBlock_1") or [], targets, ALLOWED_DATES[0], load_symbol_statuses()
    )
    raw_rows = [
        {key: value for key, value in row.items() if key in PRICE_COLUMNS}
        for row in validated["rows"]
    ]
    fundamentals, _warnings = build_fundamentals(
        validated["rows"], CAPTURE_ROOT, ALLOWED_DATES[0]
    )

    observations = _read_json(FRIDAY_KIS_ROOT / "kis_observations.json")
    adjusted_rows = []
    for raw_row in raw_rows:
        symbol = raw_row["symbol"]
        observed = (observations.get(symbol) or {}).get("adjusted") or {}
        if observed.get("status") != "ok":
            raise RecoveryError(f"Friday adjusted evidence unavailable: {symbol}")
        request_file = _read_json(FRIDAY_KIS_ROOT / "kis_raw" / f"{symbol}.json")
        adjusted_request = next(
            (
                item for item in request_file.get("requests") or []
                if (item.get("params") or {}).get("FID_ORG_ADJ_PRC") == "0"
            ),
            None,
        )
        if adjusted_request is None or not adjusted_request.get("received_at_kst"):
            raise RecoveryError(f"Friday adjusted timestamp unavailable: {symbol}")
        adjusted_rows.append({
            "symbol": symbol,
            "trade_date": ALLOWED_DATES[0],
            "open": _decimal(observed.get("open")),
            "high": _decimal(observed.get("high")),
            "low": _decimal(observed.get("low")),
            "close": _decimal(observed.get("close")),
            "volume": int(observed["volume"]),
            "source": KIS_SOURCE,
            "adjustment_basis": ADJUSTMENT_BASIS,
            "collected_at": datetime.fromisoformat(adjusted_request["received_at_kst"]),
        })
    if {r["symbol"] for r in raw_rows} != {r["symbol"] for r in adjusted_rows}:
        raise RecoveryError("Friday raw/adjusted symbol sets differ")
    if "417310" in {r["symbol"] for r in raw_rows}:
        raise RecoveryError("417310 must not receive a Friday price row")
    return raw_rows, adjusted_rows, fundamentals


def _monday_rows() -> tuple[list[dict], list[dict], list[dict]]:
    evidence = verify_monday_evidence()
    finalized = evidence["finalized"]
    root = CAPTURE_ROOT / "2026-11-23"
    raw_rows, adjusted_rows, fundamentals = [], [], []
    for symbol in evidence["symbols"]:
        record = finalized["records"][symbol]
        raw = record["raw_ohlcv"]
        adjusted = record["adjusted_ohlcv"]
        marker = _read_json(root / "finalized" / f"{symbol}.json")
        collected_at = datetime.fromisoformat(marker["finalized_at"])
        snapshot = _read_json(root / f"{symbol}.json")
        current = snapshot.get("raw_output") or {}
        # The 20:00 Capture reference price and cumulative volume can differ
        # from the next-day finalized bar; normalize_staged_fundamentals keeps
        # those provider observations as warnings.  The finalized OHLCV is
        # accepted only when its preserved strict KRX comparison matched.
        comparison = (finalized.get("krx_comparison") or {}).get(symbol) or {}
        if comparison.get("status") != "matched":
            raise RecoveryError(f"Monday Capture/Finalize price mismatch: {symbol}")
        raw_row = {
            "symbol": symbol,
            "trade_date": ALLOWED_DATES[1],
            "open": _decimal(raw["open"]),
            "high": _decimal(raw["high"]),
            "low": _decimal(raw["low"]),
            "close": _decimal(raw["close"]),
            "volume": int(raw["volume"]),
            # finalize_summary intentionally preserves OHLCV only.  Do not
            # attach the potentially earlier Capture cumulative trade value.
            "trade_value": None,
            "market_cap": None,
            "listed_shares": None,
            "source": KIS_SOURCE,
            "market_metadata_source": None,
        }
        adjusted_row = {
            "symbol": symbol,
            "trade_date": ALLOWED_DATES[1],
            "open": _decimal(adjusted["open"]),
            "high": _decimal(adjusted["high"]),
            "low": _decimal(adjusted["low"]),
            "close": _decimal(adjusted["close"]),
            "volume": int(adjusted["volume"]),
            "source": KIS_SOURCE,
            "adjustment_basis": ADJUSTMENT_BASIS,
            "collected_at": collected_at,
        }
        fundamental, _warnings = normalize_staged_fundamentals(snapshot, raw_row)
        raw_rows.append(raw_row)
        adjusted_rows.append(adjusted_row)
        fundamentals.append(fundamental)
    if "417310" in {r["symbol"] for r in raw_rows}:
        raise RecoveryError("417310 must not receive a Monday price row")
    return raw_rows, adjusted_rows, fundamentals


def build_rows(trade_date: date) -> tuple[list[dict], list[dict], list[dict]]:
    rows = _friday_rows() if trade_date == ALLOWED_DATES[0] else _monday_rows()
    if any(len(group) != 935 for group in rows):
        raise RecoveryError("Each recovery table must contain exactly 935 rows")
    return rows


def _target(url: str) -> tuple[str | None, int | None, str]:
    parsed = urlsplit(url)
    return parsed.hostname, parsed.port, parsed.path.lstrip("/")


def checked_engine(url: str):
    host, port, database = _target(url)
    if (host, port) == FORBIDDEN_TARGET:
        raise RecoveryError("The retired database target is forbidden")
    if (host, port, database) != (EXPECTED_HOST, EXPECTED_PORT, EXPECTED_DATABASE):
        raise RecoveryError("Database URL is not the approved migrated memos target")
    return create_engine(url, pool_pre_ping=True)


def _equal(actual: object, expected: object) -> bool:
    if actual is None or expected is None:
        return actual is expected
    if isinstance(actual, Decimal) or isinstance(expected, Decimal):
        return Decimal(str(actual)) == Decimal(str(expected))
    if isinstance(actual, datetime) and isinstance(expected, datetime):
        return actual == expected
    return actual == expected


def _conflicts(
    actual: dict,
    expected: dict,
    columns: Iterable[str],
    *,
    date_column: str,
) -> list[str]:
    if date_column not in expected:
        raise RecoveryError(
            f"Expected recovery row is missing date column: {date_column}"
        )
    expected_date = expected[date_column]
    differences = []
    for column in columns:
        # Monday KRX metadata is a later, allowed enrichment of the preserved
        # KIS raw row.  A non-null value is accepted only with KRX provenance.
        if (
            expected_date == ALLOWED_DATES[1]
            and column in {"market_cap", "listed_shares", "market_metadata_source"}
            and expected.get(column) is None
            and actual.get("market_metadata_source") == "KRX_OPEN_API"
        ):
            continue
        if not _equal(actual.get(column), expected.get(column)):
            differences.append(column)
    return differences


def inspect_state(connection, trade_date: date, groups: tuple[list[dict], ...], columns):
    specs = (
        ("prices_daily", "trade_date", groups[0], columns[0]),
        ("adjusted_prices_daily", "trade_date", groups[1], columns[1]),
        ("stock_fundamentals_snapshot", "basis_trade_date", groups[2], columns[2]),
    )
    result = {}
    conflicts = []
    for table, date_column, expected_rows, compare_columns in specs:
        statement = text(
            f"SELECT * FROM {table} WHERE {date_column}=:trade_date AND symbol IN :symbols"
        ).bindparams(bindparam("symbols", expanding=True))
        current = {
            str(row["symbol"]).strip(): dict(row)
            for row in connection.execute(
                statement,
                {"trade_date": trade_date, "symbols": [r["symbol"] for r in expected_rows]},
            ).mappings()
        }
        for row in expected_rows:
            actual = current.get(row["symbol"])
            if actual is None:
                continue
            differences = _conflicts(
                actual,
                row,
                compare_columns,
                date_column=date_column,
            )
            if differences:
                conflicts.append({"table": table, "symbol": row["symbol"], "columns": differences})
        result[table] = {
            "expected": len(expected_rows),
            "existing_identical": len(current) - sum(1 for x in conflicts if x["table"] == table),
            "missing": len(expected_rows) - len(current),
        }
    return result, conflicts


def insert_missing(connection, trade_date: date, groups: tuple[list[dict], ...], columns):
    specs = (
        ("prices_daily", "trade_date", groups[0], columns[0]),
        ("adjusted_prices_daily", "trade_date", groups[1], columns[1]),
        ("stock_fundamentals_snapshot", "basis_trade_date", groups[2], columns[2]),
    )
    inserted = {}
    for table, date_column, expected_rows, insert_columns in specs:
        present = set(connection.execute(
            text(f"SELECT symbol FROM {table} WHERE {date_column}=:trade_date"),
            {"trade_date": trade_date},
        ).scalars())
        missing = [row for row in expected_rows if row["symbol"] not in present]
        if missing:
            names = ", ".join(insert_columns)
            values = ", ".join(f":{name}" for name in insert_columns)
            connection.execute(text(f"INSERT INTO {table} ({names}) VALUES ({values})"), missing)
        inserted[table] = len(missing)
    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True, choices=ALLOWED_DATES)
    parser.add_argument("--apply", action="store_true", help="insert missing rows after strict preflight")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env()
    import os

    url_name = "DATABASE_URL" if args.apply else "READONLY_DATABASE_URL"
    url = os.environ.get(url_name)
    if not url:
        raise RecoveryError(f"{url_name} is missing")
    engine = checked_engine(url)
    groups = build_rows(args.trade_date)
    fundamental_columns = list(FUNDAMENTAL_COLUMNS_0023)
    with engine.connect() as connection:
        identity = connection.execute(text(
            "SELECT current_database(), current_user, inet_server_port()"
        )).one()
        if identity[0] != EXPECTED_DATABASE or identity[2] != EXPECTED_PORT:
            raise RecoveryError("Connected database identity is not approved")
        schema_columns = {c["name"] for c in inspect(connection).get_columns("stock_fundamentals_snapshot")}
        has_analysis = {"analysis_per", "analysis_pbr"} <= schema_columns
        if len({"analysis_per", "analysis_pbr"} & schema_columns) == 1:
            raise RecoveryError("Partial 0024 schema detected")
        if has_analysis and args.trade_date == ALLOWED_DATES[0]:
            fundamental_columns.extend(("analysis_per", "analysis_pbr"))
        columns = (list(PRICE_COLUMNS), list(ADJUSTED_COLUMNS), fundamental_columns)
        state, conflicts = inspect_state(connection, args.trade_date, groups, columns)
        output = {
            "mode": "apply" if args.apply else "plan",
            "trade_date": args.trade_date.isoformat(),
            "database": identity[0],
            "database_user": identity[1],
            "server_port": identity[2],
            "http_requests": 0,
            "migration_0024_columns_present": has_analysis,
            "analysis_ratios_deferred": not has_analysis and args.trade_date == ALLOWED_DATES[0],
            "tables": state,
            "conflict_count": len(conflicts),
            "conflicts": conflicts[:20],
            "hold_047400_untouched": True,
            "excluded_price_symbols": ["417310"],
        }
        if conflicts:
            print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
            return 3
    if args.apply:
        with engine.begin() as connection:
            # Recheck inside the write transaction; no insertion occurs if a
            # conflicting row appeared after the read-only preflight.
            _state, conflicts = inspect_state(connection, args.trade_date, groups, columns)
            if conflicts:
                raise RecoveryError("A conflicting row appeared before insert")
            output["inserted"] = insert_missing(connection, args.trade_date, groups, columns)
        with engine.connect() as connection:
            after, conflicts = inspect_state(connection, args.trade_date, groups, columns)
        if conflicts or any(item["missing"] for item in after.values()):
            raise RecoveryError("Post-insert verification failed")
        output["tables_after"] = after
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
