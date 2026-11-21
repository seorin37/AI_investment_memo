#!/usr/bin/env python3
"""Plan or explicitly execute bounded recovery for the 2026-11-18 outage."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import requests

from pipelines.daily_refresh import daily_refresh_lock
from pipelines.market.kis import KisClient, save_kis_prices
from pipelines.market.kis_fundamentals import (
    RAW_SNAPSHOT_ROOT,
    apply_savers,
    finalize_snapshots,
)
from pipelines.market.krx import fetch_kosdaq_daily, fetch_kospi_daily
from pipelines.market.metadata import fetch_market_metadata, save_market_metadata

from pipelines.market.kis_recovery import (
    DEFAULT_MANIFEST,
    DEFAULT_RECOVERY_ROOT,
    CappedSession,
    RecoverySafetyError,
    TRADE_DATE,
    assert_safe_execution_window,
    atomic_json,
    checkpoint_symbols,
    existing_price_symbols,
    load_manifest,
    make_batches,
    opsq0008_streak,
    recover_price_batch,
    save_metadata_missing_only,
    select_batches,
    should_stop_for_opsq0008,
    validate_manifest,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--trade-date", type=date.fromisoformat, default=TRADE_DATE)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument(
        "--mode", choices=("plan", "finalize", "prices", "metadata"), default="plan"
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="네트워크 실행 허용. 이 플래그가 없으면 plan만 출력합니다.",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="DB 저장 허용. --execute와 함께 사용해야 합니다.",
    )
    parser.add_argument("--max-kis-requests", type=int)
    parser.add_argument("--max-krx-requests", type=int, default=2)
    parser.add_argument("--max-consecutive-opsq0008", type=int, default=5)
    parser.add_argument(
        "--batch-number", type=int,
        help="1부터 시작하는 단일 배치 번호. 제한 복구 승인 시 사용합니다.",
    )
    parser.add_argument(
        "--max-batches", type=int,
        help="이번 실행에서 시작할 최대 배치 수.",
    )
    parser.add_argument("--recovery-root", type=Path, default=DEFAULT_RECOVERY_ROOT)
    args = parser.parse_args(argv)
    if args.apply and not args.execute:
        parser.error("--apply는 --execute와 함께 사용해야 합니다.")
    if args.trade_date != TRADE_DATE:
        parser.error("이 복구 도구는 --trade-date 2026-11-18만 허용합니다.")
    if args.mode != "plan" and not args.execute:
        parser.error("실행 mode에는 --execute가 필요합니다. 계획은 --mode plan을 사용하세요.")
    return args


def build_plan(args) -> dict:
    manifest = load_manifest(args.manifest)
    evidence = validate_manifest(manifest)
    finalize_batches = make_batches(evidence["finalize_symbols"], args.batch_size)
    price_batches = make_batches(evidence["price_only_symbols"], args.batch_size)
    selected_finalize = (
        select_batches(
            finalize_batches,
            batch_number=args.batch_number,
            max_batches=args.max_batches,
        )
        if args.mode in {"plan", "finalize"}
        else []
    )
    selected_prices = (
        select_batches(
            price_batches,
            batch_number=args.batch_number,
            max_batches=args.max_batches,
        )
        if args.mode in {"plan", "prices"}
        else []
    )
    return {
        "trade_date": manifest["trade_date"],
        "evidence_valid": True,
        "completed_excluded": len(evidence["completed_symbols"]),
        "finalize": {
            "symbols": len(evidence["finalize_symbols"]),
            "batches": [list(batch) for batch in finalize_batches],
            "selected_batches": [
                {"batch": number, "symbols": list(batch)}
                for number, batch in selected_finalize
            ],
            "expected_kis_requests": len(evidence["finalize_symbols"]) * 2,
            "recommended_request_cap": 400,
            "uses_existing_capture_json": True,
        },
        "price_only": {
            "symbols": len(evidence["price_only_symbols"]),
            "batches": [list(batch) for batch in price_batches],
            "selected_batches": [
                {"batch": number, "symbols": list(batch)}
                for number, batch in selected_prices
            ],
            "expected_kis_requests": len(evidence["price_only_symbols"]) * 2,
            "recommended_request_cap": 320,
            "creates_fundamentals": False,
            "creates_capture_json": False,
            "creates_finalize_marker": False,
        },
        "metadata": {
            "symbols": len(evidence["finalize_symbols"]) + len(evidence["price_only_symbols"]),
            "krx_requests": "1 KOSPI (+ at most 1 KOSDAQ fallback)",
            "missing_only": True,
            "dry_run_default": True,
        },
        "opsq0008_stop_threshold": args.max_consecutive_opsq0008,
        "apply": args.apply,
    }


def main(argv=None) -> int:
    args = parse_args(argv)
    plan = build_plan(args)
    if args.mode != "plan":
        try:
            result = execute(args)
        except RecoverySafetyError as exc:
            print(f"안전 점검 실패: {exc}", file=sys.stderr)
            return 3
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 1 if result.get("failed_symbols") else 0
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


class _KrxBudget:
    def __init__(self, maximum: int) -> None:
        if maximum < 1:
            raise RecoverySafetyError("KRX 요청 상한은 1 이상이어야 합니다.")
        self.maximum = maximum
        self.requests = 0

    def _take(self) -> None:
        if self.requests >= self.maximum:
            raise RecoverySafetyError(f"KRX 요청 상한 {self.maximum}회를 초과할 수 없습니다.")
        self.requests += 1

    def kospi(self, trade_date):
        self._take()
        return fetch_kospi_daily(trade_date, max_attempts=1)

    def kosdaq(self, trade_date):
        self._take()
        return fetch_kosdaq_daily(trade_date, max_attempts=1)


def _krx_map(budget: _KrxBudget) -> dict[str, dict]:
    return {
        str(row.get("ISU_CD") or "").strip(): row
        for row in budget.kospi(TRADE_DATE)
    }


def _client(max_requests: int) -> tuple[KisClient, CappedSession]:
    session = CappedSession(requests.Session(), max_requests)
    return KisClient(session=session), session


def execute(args) -> dict:
    assert_safe_execution_window()
    manifest = load_manifest(args.manifest)
    evidence = validate_manifest(manifest)
    default_cap = 400 if args.mode == "finalize" else 320
    cap = args.max_kis_requests or default_cap
    if cap < 1:
        raise RecoverySafetyError("요청 상한은 1 이상이어야 합니다.")
    args.recovery_root.mkdir(parents=True, exist_ok=True)

    with daily_refresh_lock() as acquired:
        if not acquired:
            raise RecoverySafetyError("시장데이터 advisory lock을 확보하지 못했습니다.")
        # Close the check/use gap: summaries, hashes and marker partition are
        # verified again immediately after taking the shared market-data lock.
        evidence = validate_manifest(manifest)
        if args.mode == "finalize":
            return _execute_finalize(args, evidence, cap)
        if args.mode == "prices":
            return _execute_prices(args, evidence, cap)
        if args.mode == "metadata":
            return _execute_metadata(args, evidence)
    raise RecoverySafetyError("지원하지 않는 실행 mode입니다.")


def _execute_finalize(args, evidence: dict, cap: int) -> dict:
    krx_budget = _KrxBudget(args.max_krx_requests)
    krx_rows = _krx_map(krx_budget)
    client, session = _client(cap)
    price_saver = fundamentals_saver = None
    if args.apply:
        price_saver, fundamentals_saver = apply_savers()
    aggregate = {
        "trade_date": TRADE_DATE.isoformat(), "mode": "finalize",
        "apply": args.apply, "batches": [], "failed_symbols": [],
        "saved_symbols": [], "stopped_for_opsq0008": False,
        "opsq0008_count": 0,
    }
    try:
        selected = select_batches(
            make_batches(evidence["finalize_symbols"], args.batch_size),
            batch_number=args.batch_number, max_batches=args.max_batches,
        )
        for index, batch in selected:
            before = client.request_metrics()
            result = finalize_snapshots(
                batch, TRADE_DATE, client=client, root=RAW_SNAPSHOT_ROOT,
                krx_rows=krx_rows, krx_strict=True,
                price_saver=price_saver, fundamentals_saver=fundamentals_saver,
                summary_path=args.recovery_root / f"finalize_batch_{index:02d}.json",
            )
            errors = [result.get("errors", {}).get(symbol, {}).get("error", "") for symbol in batch]
            record = {
                "batch": index, "symbols": list(batch),
                "requests_before": before, "requests_after": client.request_metrics(),
                "saved_symbols": result["saved_symbols"],
                "failed_symbols": result["failed_symbols"],
                "opsq0008_longest_streak": opsq0008_streak(errors),
            }
            aggregate["batches"].append(record)
            aggregate["saved_symbols"].extend(result["saved_symbols"])
            aggregate["failed_symbols"].extend(result["failed_symbols"])
            aggregate["opsq0008_count"] += sum("OPSQ0008" in error for error in errors)
            atomic_json(args.recovery_root / "finalize_recovery_summary.json", aggregate)
            if should_stop_for_opsq0008(errors, args.max_consecutive_opsq0008):
                aggregate["stopped_for_opsq0008"] = True
                break
    finally:
        session.close()
    aggregate["request_metrics"] = client.request_metrics()
    aggregate["krx_request_count"] = krx_budget.requests
    atomic_json(args.recovery_root / "finalize_recovery_summary.json", aggregate)
    return aggregate


def _execute_prices(args, evidence: dict, cap: int) -> dict:
    allowed = evidence["price_only_symbols"]
    existing = existing_price_symbols(allowed)
    krx_budget = _KrxBudget(args.max_krx_requests)
    krx_rows = _krx_map(krx_budget)
    client, session = _client(cap)
    checkpoint_path = args.recovery_root / "price_only_checkpoint.json"
    checkpointed = checkpoint_symbols(checkpoint_path)
    aggregate = {
        "trade_date": TRADE_DATE.isoformat(), "mode": "prices",
        "apply": args.apply, "saved_symbols": sorted(checkpointed),
        "ready_symbols": [],
        "skipped_existing": [], "failed_symbols": [], "blocked_krx": {},
        "batches": [], "stopped_for_opsq0008": False,
        "opsq0008_count": 0,
    }
    try:
        selected = select_batches(
            make_batches(allowed, args.batch_size),
            batch_number=args.batch_number, max_batches=args.max_batches,
        )
        for index, batch in selected:
            result = recover_price_batch(
                batch, allowed_symbols=allowed, client=client, krx_rows=krx_rows,
                existing_symbols=existing,
                checkpointed_symbols=aggregate["saved_symbols"],
                saver=save_kis_prices if args.apply else None,
            )
            aggregate["ready_symbols"].extend(result.saved)
            if args.apply:
                aggregate["saved_symbols"] = sorted(
                    set(aggregate["saved_symbols"]) | set(result.saved)
                )
            aggregate["skipped_existing"].extend(result.skipped_existing)
            aggregate["failed_symbols"].extend(result.failed)
            aggregate["blocked_krx"].update(result.blocked_krx)
            streak = opsq0008_streak(result.errors_in_order)
            aggregate["opsq0008_count"] += sum(
                "OPSQ0008" in error for error in result.errors_in_order
            )
            aggregate["batches"].append({
                "batch": index, "symbols": list(batch), "saved": result.saved,
                "failed": result.failed, "blocked_krx": result.blocked_krx,
                "opsq0008_longest_streak": streak,
                "request_metrics": client.request_metrics(),
            })
            if args.apply:
                atomic_json(checkpoint_path, {
                    "trade_date": TRADE_DATE.isoformat(),
                    "saved_symbols": aggregate["saved_symbols"],
                })
            atomic_json(args.recovery_root / "price_only_summary.json", aggregate)
            if should_stop_for_opsq0008(
                result.errors_in_order, args.max_consecutive_opsq0008
            ):
                aggregate["stopped_for_opsq0008"] = True
                break
    finally:
        session.close()
    aggregate["request_metrics"] = client.request_metrics()
    aggregate["krx_request_count"] = krx_budget.requests
    atomic_json(args.recovery_root / "price_only_summary.json", aggregate)
    return aggregate


def _execute_metadata(args, evidence: dict) -> dict:
    allowed = tuple(evidence["finalize_symbols"] + evidence["price_only_symbols"])
    krx_budget = _KrxBudget(args.max_krx_requests)
    rows = fetch_market_metadata(
        TRADE_DATE, symbols=allowed,
        fetcher=krx_budget.kospi, kosdaq_fetcher=krx_budget.kosdaq,
    )
    result = save_metadata_missing_only(
        list(rows), allowed_symbols=allowed,
        saver=save_market_metadata if args.apply else None,
    )
    payload = {
        "trade_date": TRADE_DATE.isoformat(), "mode": "metadata",
        "requested_symbols": len(allowed), "received_rows": len(rows), **result,
        "krx_request_count": krx_budget.requests,
    }
    atomic_json(args.recovery_root / "metadata_summary.json", payload)
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
