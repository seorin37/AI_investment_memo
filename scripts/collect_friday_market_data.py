#!/usr/bin/env python3
"""Run the operational Saturday KRX and Monday KIS Friday-finality stages."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from pipelines.common.db import load_env
from pipelines.daily_refresh import daily_refresh_lock
from pipelines.market.friday import (
    ADJUSTED_FINALIZED,
    MONDAY_WINDOW,
    RAW_READY,
    REQUEST_CAP_EXTRA,
    SATURDAY_WINDOW,
    STATE_ROOT,
    assert_friday_schema,
    automatic_trade_date,
    monday_deadline,
    run_monday,
    run_saturday,
    validate_recovery_trade_date,
    within_window,
)
from pipelines.market.kis import KisClient
from pipelines.market.kis_recovery import CappedSession


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=str, default=str(STATE_ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("saturday-auto")
    sub.add_parser("monday-auto")
    for name in ("saturday-recovery", "monday-recovery"):
        command = sub.add_parser(name)
        command.add_argument("--trade-date", type=date.fromisoformat, required=True)
    return parser.parse_args(argv)


def _enabled() -> bool:
    load_env()
    return os.getenv("FRIDAY_MARKET_PIPELINE_ENABLED", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _trade_date(args: argparse.Namespace, now: datetime) -> tuple[date | None, bool]:
    recovery = args.command.endswith("-recovery")
    if recovery:
        validate_recovery_trade_date(args.trade_date, now)
        return args.trade_date, True
    stage = "saturday" if args.command.startswith("saturday") else "monday"
    return automatic_trade_date(now, stage), False


def _run_locked(
    args: argparse.Namespace,
    trade_date: date,
    recovery: bool,
    now: datetime,
    state_root: Path,
) -> int:
    with daily_refresh_lock() as acquired:
        if not acquired:
            _emit({"status": "skipped_concurrent", "trade_date": trade_date.isoformat()})
            return 2
        # Fail before any provider request if migration 0024 is not applied.
        assert_friday_schema()
        if args.command.startswith("saturday"):
            result = run_saturday(trade_date, state_root=state_root)
            _emit(result)
            return 0 if result.get("status") == RAW_READY else 1

        deadline = monday_deadline(trade_date, now, delayed_recovery=recovery)
        saturday_summary_path = state_root / trade_date.isoformat() / "saturday_summary.json"
        saturday = json.loads(saturday_summary_path.read_text(encoding="utf-8"))
        targets = int((saturday.get("validation") or {}).get("response_count") or 0)
        if targets < 1:
            raise RuntimeError("토요일 비교 대상 종목 수가 없습니다.")
        cap = 2 * targets + REQUEST_CAP_EXTRA
        session = CappedSession(requests.Session(), cap)
        client = KisClient(session=session, max_attempts=2)
        try:
            result = run_monday(
                trade_date,
                client=client,
                state_root=state_root,
                deadline=deadline,
                request_cap=cap,
                delayed_recovery=recovery,
            )
        finally:
            client.close()
            session.close()
        _emit(result)
        return 0 if result.get("status") == ADJUSTED_FINALIZED else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not _enabled():
        _emit({
            "status": "disabled",
            "error": "FRIDAY_MARKET_PIPELINE_ENABLED=true 승인 후에만 실행합니다.",
        })
        return 3
    now = datetime.now(timezone.utc)
    try:
        trade_date, recovery = _trade_date(args, now)
    except Exception as exc:
        _emit({"status": "blocked", "error_type": type(exc).__name__, "error": str(exc)})
        return 4
    if trade_date is None:
        _emit({"status": "skipped_no_friday_session", "command": args.command})
        return 0
    if not recovery:
        window = SATURDAY_WINDOW if args.command.startswith("saturday") else MONDAY_WINDOW
        if not within_window(now, window):
            _emit({"status": "missed_window", "trade_date": trade_date.isoformat()})
            return 2
    state_root = Path(args.state_root)
    try:
        return _run_locked(args, trade_date, recovery, now, state_root)
    except Exception as exc:
        _emit({
            "status": "retry_required",
            "trade_date": trade_date.isoformat(),
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        })
        return 1


if __name__ == "__main__":
    sys.exit(main())
