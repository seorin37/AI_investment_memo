"""매일 09:00 Asia/Seoul 시장·경제 데이터 증분 갱신.

기존 KRX/ECOS/FRED 백필 함수를 짧은 재조회 구간에 대해 실행한다. 각 저장
함수는 UPSERT이므로 늦게 공표되거나 수정된 관측치도 안전하게 반영된다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

from pipelines.common.db import database_url
from pipelines.economic.pipeline import backfill_ecos, backfill_fred
from pipelines.market.pipeline import (
    TEST_SYMBOLS,
    backfill_gold_prices,
    backfill_market_indices,
    backfill_prices,
)

SEOUL = ZoneInfo("Asia/Seoul")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_LOG_DIR = PROJECT_ROOT / "logs" / "daily_refresh"
ADVISORY_LOCK_KEY = 581_094_001


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    def to_dict(self) -> dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


@dataclass(frozen=True)
class RefreshPlan:
    as_of: date
    krx: DateRange
    ecos: DateRange
    fred: DateRange

    def to_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "krx": self.krx.to_dict(),
            "ecos": self.ecos.to_dict(),
            "fred": self.fred.to_dict(),
        }


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name}은 정수여야 합니다: {raw}") from exc
    if value < 1:
        raise ValueError(f"{name}은 1 이상이어야 합니다.")
    return value


def build_refresh_plan(as_of: date) -> RefreshPlan:
    """공표 지연과 수정 가능성을 고려한 소스별 재조회 구간을 만든다."""
    krx_lag = _positive_int_env("DAILY_REFRESH_KRX_LAG_DAYS", 1)
    ecos_lag = _positive_int_env("DAILY_REFRESH_ECOS_LAG_DAYS", 1)
    fred_lag = _positive_int_env("DAILY_REFRESH_FRED_LAG_DAYS", 1)
    krx_days = _positive_int_env("DAILY_REFRESH_KRX_REQUERY_DAYS", 7)
    ecos_days = _positive_int_env("DAILY_REFRESH_ECOS_REQUERY_DAYS", 35)
    fred_days = _positive_int_env("DAILY_REFRESH_FRED_REQUERY_DAYS", 35)

    def window(lag_days: int, requery_days: int) -> DateRange:
        end = as_of - timedelta(days=lag_days)
        return DateRange(start=end - timedelta(days=requery_days - 1), end=end)

    return RefreshPlan(
        as_of=as_of,
        krx=window(krx_lag, krx_days),
        ecos=window(ecos_lag, ecos_days),
        fred=window(fred_lag, fred_days),
    )


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
    temporary.replace(path)


class RunLog:
    """중단 시에도 마지막 완료 단계를 알 수 있는 원자적 실행 로그."""

    def __init__(self, plan: RefreshPlan, root: Path = RUN_LOG_DIR):
        now = datetime.now(timezone.utc)
        self.run_id = f"{now:%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
        self.path = root / "runs" / f"{self.run_id}.json"
        self.latest_path = root / "latest.json"
        self.data = {
            "run_id": self.run_id,
            "status": "running",
            "started_at": now.isoformat(),
            "finished_at": None,
            "plan": plan.to_dict(),
            "steps": {},
        }
        self.save()

    def save(self) -> None:
        _atomic_json(self.path, self.data)
        _atomic_json(self.latest_path, self.data)

    def record_step(self, name: str, status: str, result: object) -> None:
        self.data["steps"][name] = {
            "status": status,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
        }
        self.save()

    def finish(self, status: str, error: str | None = None) -> None:
        self.data["status"] = status
        self.data["finished_at"] = datetime.now(timezone.utc).isoformat()
        if error:
            self.data["error"] = error
        self.save()


@contextmanager
def daily_refresh_lock() -> Iterator[bool]:
    """같은 PostgreSQL을 사용하는 일일 갱신이 하나만 실행되게 한다."""
    engine = create_engine(database_url(), pool_pre_ping=True)
    connection = engine.connect()
    acquired = False
    try:
        acquired = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"),
                {"key": ADVISORY_LOCK_KEY},
            ).scalar_one()
        )
        yield acquired
    finally:
        if acquired:
            connection.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": ADVISORY_LOCK_KEY},
            )
        connection.close()
        engine.dispose()


def _result_failed(name: str, result: dict) -> bool:
    if name == "prices":
        return bool(result.get("failed_dates") or result.get("empty_dates"))
    if name in {"indices", "gold"}:
        return bool(result.get("failed") or result.get("empty_market"))
    return bool(result.get("failed"))


def default_steps(
    plan: RefreshPlan,
    request_interval: float,
) -> list[tuple[str, Callable[[], dict]]]:
    """기존 파이프라인을 재조회 모드로 호출하는 순서를 반환한다."""
    return [
        (
            "prices",
            lambda: backfill_prices(
                start_date=plan.krx.start,
                end_date=plan.krx.end,
                symbols=TEST_SYMBOLS,
                request_interval=request_interval,
                scope="test",
                resume=False,
            ),
        ),
        (
            "indices",
            lambda: backfill_market_indices(
                start_date=plan.krx.start,
                end_date=plan.krx.end,
                request_interval=request_interval,
                resume=False,
            ),
        ),
        (
            "gold",
            lambda: backfill_gold_prices(
                start_date=plan.krx.start,
                end_date=plan.krx.end,
                request_interval=request_interval,
                resume=False,
            ),
        ),
        (
            "ecos",
            lambda: backfill_ecos(
                start_date=plan.ecos.start,
                end_date=plan.ecos.end,
                request_interval=request_interval,
                resume=False,
            ),
        ),
        (
            "fred",
            lambda: backfill_fred(
                start_date=plan.fred.start,
                end_date=plan.fred.end,
                request_interval=request_interval,
                resume=False,
            ),
        ),
    ]


def run_refresh(
    plan: RefreshPlan,
    request_interval: float = 0.5,
    log_root: Path = RUN_LOG_DIR,
    steps: list[tuple[str, Callable[[], dict]]] | None = None,
) -> dict:
    """계획을 실행하고 단계별 결과 및 프로세스 종료 판단을 반환한다."""
    if request_interval < 0:
        raise ValueError("request_interval은 0 이상이어야 합니다.")

    run_log = RunLog(plan, root=log_root)
    summary = {"run_id": run_log.run_id, "status": "running", "steps": {}}

    try:
        with daily_refresh_lock() as acquired:
            if not acquired:
                summary["status"] = "skipped_concurrent"
                run_log.finish("skipped_concurrent")
                return summary

            has_failure = False
            for name, runner in steps or default_steps(plan, request_interval):
                try:
                    result = runner()
                    failed = _result_failed(name, result)
                    status = "failed" if failed else "success"
                except Exception as exc:
                    result = {
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                    status = "failed"
                has_failure = has_failure or status == "failed"
                summary["steps"][name] = {"status": status, "result": result}
                run_log.record_step(name, status, result)

            summary["status"] = "failed" if has_failure else "success"
            run_log.finish(summary["status"])
            return summary
    except Exception as exc:
        run_log.finish("failed", f"{type(exc).__name__}: {exc}")
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        help="서울 기준 실행일(YYYY-MM-DD). 기본값은 현재 날짜",
    )
    parser.add_argument(
        "--request-interval",
        type=float,
        default=0.5,
        help="외부 API 요청 사이 대기 시간(초)",
    )
    parser.add_argument(
        "--print-plan",
        action="store_true",
        help="외부 API/DB를 호출하지 않고 날짜 계획만 출력",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    as_of = args.as_of or datetime.now(SEOUL).date()
    plan = build_refresh_plan(as_of)

    if args.print_plan:
        print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
        return 0

    summary = run_refresh(plan, request_interval=args.request_interval)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 1 if summary["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
