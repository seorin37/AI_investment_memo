#!/usr/bin/env python3
"""Measure when KIS daily bars and quote fundamentals become stable.

This diagnostic never connects to the database.  A normal probe makes exactly
three quotation requests per symbol (raw daily, adjusted daily, current quote)
for the fixed three-symbol sample.  The Friday-finality experiment mode makes
one raw-daily request per explicitly selected symbol and one date-wide KRX
request.  ``--summary`` only reads the JSONL log.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

from pipelines.market.kis import (
    DAILY_PATH,
    DAILY_TR_ID,
    PRICE_PATH,
    PRICE_TR_ID,
    KisClient,
)
from pipelines.common.db import load_env
from pipelines.market.krx import KRX_URL, fetch_kospi_daily


SEOUL = ZoneInfo("Asia/Seoul")
MARKET_CODE = "J"
SYMBOLS = ("005930", "000080", "000020")
SLOT_ORDER = {
    "2200": 0,
    "0200": 1,
    "0800": 2,
    "fri2000": 10,
    "sat0800": 11,
    "sat1200": 12,
    "sun0800": 13,
    "mon0800": 14,
    "mon1030": 15,
}
MARKET_SERVICES = (
    "memos-market-refresh-morning.service",
    "memos-market-refresh-evening.service",
    "memos-kis-two-stage-capture.service",
    "memos-kis-two-stage-finalize.service",
)
DEFAULT_LOG_DIR = (
    Path(__file__).resolve().parents[1]
    / "logs"
    / "diagnostics"
    / "kis_daily_stability"
)
CURRENT_FIELDS = (
    "stck_prpr",
    "acml_vol",
    "stck_sdpr",
    "per",
    "pbr",
    "eps",
    "bps",
    "stck_bsop_date",
    "stck_cntg_hour",
    "stck_prdy_clpr",
    "rprs_mrkt_kor_name",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trade-date",
        required=True,
        type=date.fromisoformat,
        help="비교할 KRX 거래일 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--slot",
        choices=tuple(SLOT_ORDER),
        help="진단 실행 슬롯",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=list(SYMBOLS),
        help="진단할 종목코드(기본 3종목)",
    )
    parser.add_argument(
        "--raw-krx-only",
        action="store_true",
        help="원시 KIS 일봉만 조회하고 같은 날짜 KRX 정규장 OHLCV와 비교",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="API 호출 없이 해당 거래일의 JSONL 로그를 비교 출력",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    args.symbols = tuple(dict.fromkeys(str(symbol).strip().upper() for symbol in args.symbols))
    if any(len(symbol) != 6 or not symbol.isalnum() for symbol in args.symbols):
        parser.error("--symbols는 6자리 영문 대문자 또는 숫자여야 합니다.")
    if not args.summary and args.slot is None:
        parser.error("진단 실행에는 --slot이 필요합니다.")
    if args.summary and args.slot is not None:
        parser.error("--summary와 --slot은 함께 사용할 수 없습니다.")
    return args


def active_market_services(
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> list[str]:
    """Return active market services, failing closed if systemd is unavailable."""
    active: list[str] = []
    for service in MARKET_SERVICES:
        result = runner(
            ["systemctl", "--user", "is-active", "--quiet", service],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            active.append(service)
        elif result.returncode != 3:
            raise RuntimeError(
                f"systemd 서비스 상태를 안전하게 확인하지 못했습니다: {service}"
            )
    return active


def _decimal(value: object) -> Decimal | None:
    text = str(value or "").replace(",", "").strip()
    if text in {"", "-"}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _integer(value: object) -> int | None:
    parsed = _decimal(value)
    if parsed is None or parsed != parsed.to_integral_value():
        return None
    return int(parsed)


def _decimal_string(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _safe_error(exc: Exception) -> dict[str, str]:
    return {
        "status": "error",
        "error_type": type(exc).__name__,
        "error": str(exc)[:200],
    }


def _daily_observation(
    client: KisClient,
    symbol: str,
    trade_date: date,
    *,
    adjusted: bool,
    now: Callable[[], datetime],
) -> dict:
    requested_at = now()
    try:
        rows = client.daily_page(
            symbol,
            trade_date,
            trade_date,
            adjusted=adjusted,
        )
        received_at = now()
        target = trade_date.strftime("%Y%m%d")
        row = next((item for item in rows if item.get("stck_bsop_date") == target), None)
        if row is None:
            payload = {"status": "no_row"}
        else:
            payload = {
                "status": "ok",
                "trade_date": row.get("stck_bsop_date"),
                "open": row.get("stck_oprc"),
                "high": row.get("stck_hgpr"),
                "low": row.get("stck_lwpr"),
                "close": row.get("stck_clpr"),
                "volume": row.get("acml_vol"),
            }
    except Exception as exc:
        received_at = now()
        payload = _safe_error(exc)
    return {
        "request_started_at_kst": requested_at.isoformat(),
        "response_received_at_kst": received_at.isoformat(),
        "endpoint": DAILY_PATH,
        "tr_id": DAILY_TR_ID,
        "market_code": MARKET_CODE,
        "adjusted": adjusted,
        "request_params": {
            "FID_COND_MRKT_DIV_CODE": MARKET_CODE,
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": trade_date.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": trade_date.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0" if adjusted else "1",
        },
        **payload,
    }


def _current_observation(
    client: KisClient,
    symbol: str,
    *,
    now: Callable[[], datetime],
) -> dict:
    requested_at = now()
    try:
        response = client.current_price(symbol)
        received_at = now()
        payload = {
            "status": "ok",
            **{field: response.get(field) for field in CURRENT_FIELDS},
        }
    except Exception as exc:
        received_at = now()
        payload = _safe_error(exc)
    return {
        "request_started_at_kst": requested_at.isoformat(),
        "response_received_at_kst": received_at.isoformat(),
        "endpoint": PRICE_PATH,
        "tr_id": PRICE_TR_ID,
        "market_code": MARKET_CODE,
        # This endpoint has no dependable business-date field.  Do not add one.
        "basis_trade_date": None,
        **payload,
    }


def _krx_daily_observations(
    trade_date: date,
    symbols: Iterable[str],
    *,
    fetcher: Callable[[date], list[dict]] = fetch_kospi_daily,
    now: Callable[[], datetime],
) -> dict[str, dict]:
    """Fetch one sanitized KRX daily snapshot for all experiment symbols."""

    symbol_list = tuple(symbols)
    requested_at = now()
    try:
        rows = fetcher(trade_date)
        received_at = now()
        lookup = {
            str(row.get("ISU_CD") or "").strip(): row
            for row in rows
            if isinstance(row, dict)
        }
        result: dict[str, dict] = {}
        for symbol in symbol_list:
            row = lookup.get(symbol)
            if row is None:
                payload = {"status": "missing"}
            else:
                payload = {
                    "status": "ok",
                    "trade_date": row.get("BAS_DD"),
                    "open": row.get("TDD_OPNPRC"),
                    "high": row.get("TDD_HGPRC"),
                    "low": row.get("TDD_LWPRC"),
                    "close": row.get("TDD_CLSPRC"),
                    "volume": row.get("ACC_TRDVOL"),
                }
            result[symbol] = {
                "request_started_at_kst": requested_at.isoformat(),
                "response_received_at_kst": received_at.isoformat(),
                "endpoint": KRX_URL,
                "request_params": {"basDd": trade_date.strftime("%Y%m%d")},
                **payload,
            }
        return result
    except Exception as exc:
        received_at = now()
        error = _safe_error(exc)
        return {
            symbol: {
                "request_started_at_kst": requested_at.isoformat(),
                "response_received_at_kst": received_at.isoformat(),
                "endpoint": KRX_URL,
                "request_params": {"basDd": trade_date.strftime("%Y%m%d")},
                **error,
            }
            for symbol in symbol_list
        }


def _krx_comparison(raw: dict, krx: dict) -> dict:
    """Compare KIS raw daily OHLCV with the sanitized KRX regular session."""

    if raw.get("status") != "ok":
        return {"status": "kis_unavailable", "mismatched_fields": []}
    if krx.get("status") != "ok":
        return {
            "status": "krx_unavailable",
            "krx_status": krx.get("status"),
            "mismatched_fields": [],
        }

    field_matches: dict[str, bool | None] = {}
    deltas: dict[str, str | None] = {}
    mismatched: list[str] = []
    for field in ("open", "high", "low", "close"):
        kis_value = _decimal(raw.get(field))
        krx_value = _decimal(krx.get(field))
        matches = None if kis_value is None or krx_value is None else kis_value == krx_value
        field_matches[field] = matches
        deltas[field] = (
            _decimal_string(kis_value - krx_value)
            if kis_value is not None and krx_value is not None
            else None
        )
        if matches is not True:
            mismatched.append(field)

    kis_volume = _integer(raw.get("volume"))
    krx_volume = _integer(krx.get("volume"))
    volume_matches = (
        None if kis_volume is None or krx_volume is None else kis_volume == krx_volume
    )
    field_matches["volume"] = volume_matches
    deltas["volume"] = (
        str(kis_volume - krx_volume)
        if kis_volume is not None and krx_volume is not None
        else None
    )
    if volume_matches is not True:
        mismatched.append("volume")

    requested_date = str(raw.get("trade_date") or "").replace("-", "")
    date_matches = requested_date == str(krx.get("trade_date") or "").strip()
    field_matches["trade_date"] = date_matches
    if not date_matches:
        mismatched.append("trade_date")
    return {
        "status": "matched" if not mismatched else "mismatched",
        "field_matches": field_matches,
        "mismatched_fields": mismatched,
        "kis_minus_krx": deltas,
        "close_matches": field_matches["close"],
    }


def _comparisons(raw: dict, current: dict) -> dict:
    raw_close = _decimal(raw.get("close")) if raw.get("status") == "ok" else None
    raw_volume = _integer(raw.get("volume")) if raw.get("status") == "ok" else None
    current_price = (
        _decimal(current.get("stck_prpr")) if current.get("status") == "ok" else None
    )
    current_volume = (
        _integer(current.get("acml_vol")) if current.get("status") == "ok" else None
    )
    standard_price = (
        _decimal(current.get("stck_sdpr")) if current.get("status") == "ok" else None
    )
    per = _decimal(current.get("per")) if current.get("status") == "ok" else None
    pbr = _decimal(current.get("pbr")) if current.get("status") == "ok" else None
    eps = _decimal(current.get("eps")) if current.get("status") == "ok" else None
    bps = _decimal(current.get("bps")) if current.get("status") == "ok" else None
    per_price = per * eps if per is not None and eps is not None else None
    pbr_price = pbr * bps if pbr is not None and bps is not None else None

    def equals(left: object, right: object) -> bool | None:
        return None if left is None or right is None else left == right

    def difference(left: Decimal | None, right: Decimal | None) -> str | None:
        return _decimal_string(left - right) if left is not None and right is not None else None

    return {
        "raw_close_equals_current_price": equals(raw_close, current_price),
        "raw_volume_equals_current_volume": equals(raw_volume, current_volume),
        "raw_close_equals_standard_price": equals(raw_close, standard_price),
        "per_times_eps": _decimal_string(per_price),
        "pbr_times_bps": _decimal_string(pbr_price),
        "per_price_minus_current": difference(per_price, current_price),
        "pbr_price_minus_current": difference(pbr_price, current_price),
        "per_price_minus_raw_close": difference(per_price, raw_close),
        "pbr_price_minus_raw_close": difference(pbr_price, raw_close),
    }


def collect_records(
    trade_date: date,
    slot: str,
    *,
    symbols: Iterable[str] = SYMBOLS,
    raw_krx_only: bool = False,
    client_factory: Callable[[], KisClient] = KisClient,
    krx_fetcher: Callable[[date], list[dict]] = fetch_kospi_daily,
    now: Callable[[], datetime] = lambda: datetime.now(SEOUL),
) -> list[dict]:
    records: list[dict] = []
    run_started = now()
    symbol_list = tuple(symbols)
    krx_observations = (
        _krx_daily_observations(
            trade_date,
            symbol_list,
            fetcher=krx_fetcher,
            now=now,
        )
        if raw_krx_only
        else {}
    )
    with client_factory() as client:
        for symbol in symbol_list:
            raw = _daily_observation(
                client, symbol, trade_date, adjusted=False, now=now
            )
            if raw_krx_only:
                adjusted = {"status": "not_requested"}
                current = {"status": "not_requested", "basis_trade_date": None}
                krx = krx_observations[symbol]
                krx_comparison = _krx_comparison(raw, krx)
            else:
                adjusted = _daily_observation(
                    client, symbol, trade_date, adjusted=True, now=now
                )
                current = _current_observation(client, symbol, now=now)
                krx = {"status": "not_requested"}
                krx_comparison = {"status": "not_requested"}
            records.append(
                {
                    "schema_version": 1,
                    "probe_mode": "raw_krx_only" if raw_krx_only else "full",
                    "run_started_at_kst": run_started.isoformat(),
                    "run_finished_at_kst": now().isoformat(),
                    "slot": slot,
                    "requested_trade_date": trade_date.isoformat(),
                    "symbol": symbol,
                    "raw_daily": raw,
                    "adjusted_daily": adjusted,
                    "current_quote": current,
                    "comparisons": _comparisons(raw, current),
                    "krx_daily": krx,
                    "krx_comparison": krx_comparison,
                }
            )
    return records


def log_path(log_dir: Path, trade_date: date) -> Path:
    return log_dir / f"{trade_date:%Y%m%d}.jsonl"


def append_records(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    os.chmod(path, 0o600)


def read_records(path: Path, trade_date: date) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL {line_number}행이 손상됐습니다.") from exc
            if record.get("requested_trade_date") == trade_date.isoformat():
                records.append(record)
    return records


def _raw_changes(previous: dict | None, current: dict) -> dict:
    if previous is None:
        return {"changed_fields": [], "deltas": {}}
    previous_raw = previous.get("raw_daily", {})
    current_raw = current.get("raw_daily", {})
    if previous_raw.get("status") != "ok" or current_raw.get("status") != "ok":
        return {"changed_fields": [], "deltas": {}, "comparison_unavailable": True}
    changed: list[str] = []
    deltas: dict[str, str] = {}
    for field in ("open", "high", "low", "close", "volume"):
        before = _decimal(previous_raw.get(field))
        after = _decimal(current_raw.get(field))
        if before is None or after is None:
            continue
        if before != after:
            changed.append(field)
            deltas[field] = _decimal_string(after - before) or "0"
    return {"changed_fields": changed, "deltas": deltas}


def build_summary(
    records: Iterable[dict],
    trade_date: date,
    symbols: Iterable[str] = SYMBOLS,
) -> dict:
    symbol_list = tuple(symbols)
    latest: dict[tuple[str, str], dict] = {}
    for record in records:
        symbol = str(record.get("symbol", ""))
        slot = str(record.get("slot", ""))
        if symbol not in symbol_list or slot not in SLOT_ORDER:
            continue
        key = (symbol, slot)
        if key not in latest or str(record.get("run_finished_at_kst", "")) >= str(
            latest[key].get("run_finished_at_kst", "")
        ):
            latest[key] = record

    symbol_summaries: dict[str, dict] = {}
    for symbol in symbol_list:
        timeline = [
            latest[(symbol, slot)]
            for slot in sorted(SLOT_ORDER, key=SLOT_ORDER.get)
            if (symbol, slot) in latest
        ]
        raw_ok = [item["raw_daily"] for item in timeline if item["raw_daily"].get("status") == "ok"]
        close_values = [item.get("close") for item in raw_ok]
        volume_values = [item.get("volume") for item in raw_ok]

        def stable_since(field: str) -> str | None:
            observations = [
                (item["slot"], item["raw_daily"].get(field))
                for item in timeline
                if item["raw_daily"].get("status") == "ok"
                and item["raw_daily"].get(field) is not None
            ]
            for index, (slot, _value) in enumerate(observations):
                suffix = [value for _slot, value in observations[index:]]
                if len(suffix) >= 2 and len(set(suffix)) == 1:
                    return slot
            return None

        timeline_rows = []
        previous = None
        for item in timeline:
            timeline_rows.append(
                {
                    "slot": item["slot"],
                    "run_started_at_kst": item.get("run_started_at_kst"),
                    "run_finished_at_kst": item.get("run_finished_at_kst"),
                    "raw_daily": item["raw_daily"],
                    "adjusted_daily": item["adjusted_daily"],
                    "current_quote": item["current_quote"],
                    "comparisons": item["comparisons"],
                    "krx_daily": item.get("krx_daily", {"status": "not_recorded"}),
                    "krx_comparison": item.get(
                        "krx_comparison", {"status": "not_recorded"}
                    ),
                    "changes_from_previous": _raw_changes(previous, item),
                }
            )
            previous = item

        symbol_summaries[symbol] = {
            "observed_slots": [item["slot"] for item in timeline],
            "raw_close_stable": len(close_values) >= 2 and len(set(close_values)) == 1,
            "raw_volume_stable": len(volume_values) >= 2 and len(set(volume_values)) == 1,
            "raw_close_stable_since": stable_since("close"),
            "raw_volume_stable_since": stable_since("volume"),
            "timeline": timeline_rows,
        }

    slot_summary = []
    for slot in sorted(SLOT_ORDER, key=SLOT_ORDER.get):
        rows = [latest[(symbol, slot)] for symbol in symbol_list if (symbol, slot) in latest]
        if not rows:
            continue
        changes = {
            row["symbol"]: next(
                item["changes_from_previous"]
                for item in symbol_summaries[row["symbol"]]["timeline"]
                if item["slot"] == slot
            )
            for row in rows
        }
        slot_summary.append(
            {
                "slot": slot,
                "observed_symbols": len(rows),
                "krx_full_match": sum(
                    row.get("krx_comparison", {}).get("status") == "matched"
                    for row in rows
                ),
                "close_match": sum(
                    row.get("krx_comparison", {}).get("close_matches") is True
                    for row in rows
                ),
                "changed_symbols": sum(
                    bool(value.get("changed_fields")) for value in changes.values()
                ),
                "changes_from_previous": changes,
            }
        )
    return {
        "trade_date": trade_date.isoformat(),
        "symbols": symbol_summaries,
        "slot_summary": slot_summary,
    }


def main(
    argv: list[str] | None = None,
    *,
    client_factory: Callable[[], KisClient] = KisClient,
    krx_fetcher: Callable[[date], list[dict]] = fetch_kospi_daily,
    service_checker: Callable[[], list[str]] = active_market_services,
    now: Callable[[], datetime] = lambda: datetime.now(SEOUL),
) -> int:
    args = parse_args(argv)
    path = log_path(args.log_dir, args.trade_date)
    if args.summary:
        records = read_records(path, args.trade_date)
        print(
            json.dumps(
                build_summary(records, args.trade_date, args.symbols),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    try:
        active = service_checker()
    except RuntimeError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if active:
        print(
            json.dumps(
                {
                    "status": "blocked_active_service",
                    "active_services": active,
                    "message": "시장데이터 서비스 실행 중이므로 KIS API를 호출하지 않았습니다.",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    load_env()
    records = collect_records(
        args.trade_date,
        args.slot,
        symbols=args.symbols,
        raw_krx_only=args.raw_krx_only,
        client_factory=client_factory,
        krx_fetcher=krx_fetcher,
        now=now,
    )
    append_records(path, records)
    print(
        json.dumps(
            {
                "status": "recorded",
                "trade_date": args.trade_date.isoformat(),
                "slot": args.slot,
                "symbols": list(args.symbols),
                "record_count": len(records),
                "log_path": str(path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.raw_krx_only and any(
        record["raw_daily"].get("status") != "ok"
        or record["krx_daily"].get("status") != "ok"
        for record in records
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
