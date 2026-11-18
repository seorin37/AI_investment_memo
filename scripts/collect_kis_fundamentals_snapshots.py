#!/usr/bin/env python3
"""Capture KIS fundamentals at night and finalize them after daily bars settle."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from pipelines.common.db import load_env
from pipelines.daily_refresh import daily_refresh_lock
from pipelines.market.kis import KisClient
from pipelines.market.kis_fundamentals import (
    RAW_SNAPSHOT_ROOT,
    apply_savers,
    automatic_capture_date,
    automatic_finalize_date,
    capture_target_symbols,
    capture_snapshots,
    finalize_snapshots,
    mark_terminal_inactive,
    operational_symbols,
    pending_snapshot_dates,
    symbols_needing_finalization,
)
from pipelines.market.krx import fetch_kospi_daily, fetch_kospi_stock_master
from pipelines.market.stock_master import load_kospi_symbols, normalize_kospi_snapshot
from pipelines.market.symbol_status import load_symbol_statuses, select_operational_symbols


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-root",
        type=Path,
        default=RAW_SNAPSHOT_ROOT,
        help="원본·요약 파일 경로",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("capture", "finalize"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--trade-date", type=date.fromisoformat, required=True)
        sub.add_argument("--symbols", nargs="+")
        sub.add_argument("--symbol-limit", type=int)
    subparsers.choices["capture"].add_argument("--overwrite", action="store_true")
    subparsers.choices["finalize"].add_argument(
        "--apply",
        action="store_true",
        help="명시한 경우에만 기존 UPSERT 함수로 DB에 저장",
    )
    subparsers.choices["finalize"].add_argument(
        "--verify-krx",
        action="store_true",
        help="KRX 공식 정규장 OHLCV와 일치할 때만 결합",
    )
    subparsers.choices["finalize"].add_argument(
        "--krx-warning-only",
        action="store_true",
        help="KRX 비교 실패를 로그 경고로만 남기고 유효한 KIS 데이터는 계속 처리",
    )
    for name in ("capture-auto", "finalize-auto"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--symbols", nargs="+")
        sub.add_argument("--symbol-limit", type=int)
    subparsers.choices["finalize-auto"].add_argument(
        "--recovery-days",
        type=int,
        default=10,
        help="미확정 날짜를 다시 확인할 최근 달력일 범위",
    )
    subparsers.choices["finalize-auto"].add_argument(
        "--krx-warning-only",
        action="store_true",
        help="KRX 비교 실패를 경고로 남기고 유효한 KIS 데이터는 계속 저장",
    )
    return parser.parse_args(argv)


def _two_stage_enabled() -> bool:
    load_env()
    return os.getenv("KIS_TWO_STAGE_ENABLED", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _targets(
    args: argparse.Namespace,
    *,
    trade_date: date | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...], dict]:
    selected = load_kospi_symbols(
        symbols=args.symbols,
        limit=args.symbol_limit,
    )
    if args.symbols is not None:
        return selected, (), {"selection_mode": "explicit"}
    observed = None
    observation = {"status": "not_requested"}
    if trade_date is not None:
        try:
            rows = normalize_kospi_snapshot(fetch_kospi_stock_master(trade_date))
            observed = tuple(row["symbol"] for row in rows)
            observation = {"status": "success", "received": len(observed)}
        except Exception as exc:
            # The reviewed terminal registry remains authoritative. A temporary
            # KRX failure must not empty or shrink the operating universe.
            observation = {
                "status": "unavailable",
                "error_type": type(exc).__name__,
                "error": str(exc)[:300],
            }
    selection = select_operational_symbols(
        selected,
        trade_date or date.today(),
        observed_krx_symbols=observed,
    )
    metadata = {
        "selection_mode": "operational_status",
        "db_count": selection["db_count"],
        "krx_observation": observation,
        "krx_observed_count": selection["krx_observed_count"],
        "temporarily_absent_symbols": list(selection["temporarily_absent_symbols"]),
        "pending_master_sync_symbols": list(selection["pending_master_sync_symbols"]),
    }
    return selection["symbols"], selection["terminal_symbols"], metadata


def _emit(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def _run_capture_auto(args: argparse.Namespace, now: datetime) -> tuple[dict, int]:
    trade_date = automatic_capture_date(now)
    if trade_date is None:
        return {
            "status": "skipped_non_trading_day",
            "run_date": now.astimezone().date().isoformat(),
        }, 0
    symbols, excluded, selection = _targets(args, trade_date=trade_date)
    with KisClient() as client:
        result = capture_snapshots(
            symbols,
            trade_date,
            client=client,
            root=args.state_root,
        )
    result["status"] = "failed" if result["failed_symbols"] else "success"
    result["excluded_symbols"] = list(excluded)
    result["universe_selection"] = selection
    return result, 1 if result["failed_symbols"] else 0


def _run_finalize_auto(args: argparse.Namespace, now: datetime) -> tuple[dict, int]:
    cutoff = automatic_finalize_date(now)
    dates = set(
        trade_date
        for trade_date in pending_snapshot_dates(
            args.state_root, cutoff, recovery_days=args.recovery_days
        )
        if trade_date.weekday() < 4
    )
    # Friday sessions remain staged until the separate weekend-finality policy
    # is decided. A Tuesday after a Monday holiday must not finalize Friday.
    if cutoff.weekday() < 4:
        dates.add(cutoff)
    price_saver, fundamentals_saver = apply_savers()
    result = {
        "status": "success",
        "cutoff_trade_date": cutoff.isoformat(),
        "target_count": 0,
        "processed_dates": [],
        "skipped_dates": [],
        "failed_dates": [],
        "date_results": {},
    }
    client: KisClient | None = None
    statuses = load_symbol_statuses()
    try:
        for trade_date in sorted(dates):
            try:
                symbols = capture_target_symbols(args.state_root, trade_date)
            except Exception as exc:
                result["failed_dates"].append(trade_date.isoformat())
                result["date_results"][trade_date.isoformat()] = {
                    "status": "missing_capture",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                }
                continue
            result["target_count"] = max(result["target_count"], len(symbols))
            terminal_inactive = []
            for symbol in symbols:
                status = statuses.get(symbol)
                if status is not None and status.is_terminal_on(trade_date):
                    if mark_terminal_inactive(
                        args.state_root, trade_date, symbol, status
                    ):
                        terminal_inactive.append(symbol)
            pending = symbols_needing_finalization(
                args.state_root,
                trade_date,
                symbols,
            )
            if not pending:
                result["skipped_dates"].append(trade_date.isoformat())
                result["date_results"][trade_date.isoformat()] = {
                    "status": "already_finalized",
                    "terminal_inactive_symbols": terminal_inactive,
                }
                continue
            try:
                krx_lookup_error = None
                try:
                    krx_rows = {
                        str(row.get("ISU_CD") or "").strip(): row
                        for row in fetch_kospi_daily(trade_date)
                    }
                except Exception as exc:
                    if not getattr(args, "krx_warning_only", False):
                        raise
                    krx_rows = {}
                    krx_lookup_error = f"{type(exc).__name__}: {str(exc)[:240]}"
                if client is None:
                    client = KisClient()
                finalized = finalize_snapshots(
                    pending,
                    trade_date,
                    client=client,
                    root=args.state_root,
                    krx_rows=krx_rows,
                    krx_strict=not getattr(args, "krx_warning_only", False),
                    krx_lookup_error=krx_lookup_error,
                    price_saver=price_saver,
                    fundamentals_saver=fundamentals_saver,
                )
                finalized["terminal_inactive_symbols"] = terminal_inactive
                result["date_results"][trade_date.isoformat()] = finalized
                result["processed_dates"].append(trade_date.isoformat())
                if finalized["failed_symbols"]:
                    result["failed_dates"].append(trade_date.isoformat())
            except Exception as exc:
                result["failed_dates"].append(trade_date.isoformat())
                result["date_results"][trade_date.isoformat()] = {
                    "status": "deferred",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                }
    finally:
        if client is not None:
            client.close()
    if result["failed_dates"]:
        result["status"] = "failed"
    return result, 1 if result["failed_dates"] else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command.endswith("-auto") and not _two_stage_enabled():
        _emit({
            "status": "disabled",
            "error": "KIS_TWO_STAGE_ENABLED=true 설정 후에만 자동 수집을 실행합니다.",
        })
        return 3
    with daily_refresh_lock() as acquired:
        if not acquired:
            print(
                json.dumps(
                    {
                        "status": "skipped_concurrent",
                        "error": "다른 시장데이터 수집 작업이 실행 중입니다.",
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 2
        if args.command == "capture-auto":
            result, exit_code = _run_capture_auto(
                args, datetime.now(timezone.utc)
            )
        elif args.command == "finalize-auto":
            result, exit_code = _run_finalize_auto(
                args, datetime.now(timezone.utc)
            )
        else:
            symbols = load_kospi_symbols(
                symbols=args.symbols,
                limit=args.symbol_limit,
            )
            with KisClient() as client:
                if args.command == "capture":
                    result = capture_snapshots(
                        symbols,
                        args.trade_date,
                        client=client,
                        root=args.state_root,
                        overwrite=args.overwrite,
                    )
                else:
                    krx_rows = None
                    krx_lookup_error = None
                    if args.verify_krx:
                        try:
                            krx_rows = {
                                str(row.get("ISU_CD") or "").strip(): row
                                for row in fetch_kospi_daily(args.trade_date)
                            }
                        except Exception as exc:
                            if not args.krx_warning_only:
                                raise
                            krx_rows = {}
                            krx_lookup_error = (
                                f"{type(exc).__name__}: {str(exc)[:240]}"
                            )
                    if args.apply:
                        price_saver, fundamentals_saver = apply_savers()
                    else:
                        price_saver = fundamentals_saver = None
                    result = finalize_snapshots(
                        symbols,
                        args.trade_date,
                        client=client,
                        root=args.state_root,
                        krx_rows=krx_rows,
                        krx_strict=not args.krx_warning_only,
                        krx_lookup_error=krx_lookup_error,
                        price_saver=price_saver,
                        fundamentals_saver=fundamentals_saver,
                    )
            exit_code = 1 if result["failed_symbols"] else 0
    _emit(result)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
