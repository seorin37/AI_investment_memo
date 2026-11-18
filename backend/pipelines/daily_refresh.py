"""09:00 KRX·경제, 18:30 KIS 증분 갱신.

morning 프로필은 KRX 메타데이터·지수·금과 ECOS/FRED를, evening 프로필은
KIS 확정 종목 일봉·투자지표만 실행한다.
각 저장 함수는 UPSERT이므로 늦게 공표되거나 수정된 관측치도 반영된다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

from pipelines.common.db import database_url
from pipelines.economic.pipeline import backfill_ecos, backfill_fred
from pipelines.market.calendar import is_krx_trading_day
from pipelines.market.kis import refresh_kis_market_data
from pipelines.market.metadata import backfill_market_metadata
from pipelines.market.stock_master import load_kospi_symbols, sync_kospi_stocks
from pipelines.market.pipeline import (
    backfill_gold_prices,
    backfill_market_indices,
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
    kis: DateRange
    kis_full_sync_symbol: str | None
    ecos: DateRange
    fred: DateRange

    def to_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "krx": self.krx.to_dict(),
            "kis": self.kis.to_dict(),
            "kis_full_sync_symbol": self.kis_full_sync_symbol,
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


def _nonnegative_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name}은 정수여야 합니다: {raw}") from exc
    if value < 0:
        raise ValueError(f"{name}은 0 이상이어야 합니다.")
    return value


def _boolean_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name}은 true/false 형식이어야 합니다.")


def _latest_krx_trading_day(on_or_before: date) -> date:
    target = on_or_before
    while not is_krx_trading_day(target):
        target -= timedelta(days=1)
    return target


def build_refresh_plan(as_of: date) -> RefreshPlan:
    """공표 지연과 수정 가능성을 고려한 소스별 재조회 구간을 만든다."""
    krx_lag = _positive_int_env("DAILY_REFRESH_KRX_LAG_DAYS", 1)
    kis_lag = _nonnegative_int_env("DAILY_REFRESH_KIS_LAG_DAYS", 0)
    ecos_lag = _positive_int_env("DAILY_REFRESH_ECOS_LAG_DAYS", 1)
    fred_lag = _positive_int_env("DAILY_REFRESH_FRED_LAG_DAYS", 1)
    krx_days = _positive_int_env("DAILY_REFRESH_KRX_REQUERY_DAYS", 7)
    ecos_days = _positive_int_env("DAILY_REFRESH_ECOS_REQUERY_DAYS", 35)
    fred_days = _positive_int_env("DAILY_REFRESH_FRED_REQUERY_DAYS", 35)

    def window(lag_days: int, requery_days: int) -> DateRange:
        end = as_of - timedelta(days=lag_days)
        return DateRange(start=end - timedelta(days=requery_days - 1), end=end)

    kis_date = as_of - timedelta(days=kis_lag)
    while not is_krx_trading_day(kis_date):
        kis_date -= timedelta(days=1)

    return RefreshPlan(
        as_of=as_of,
        krx=window(krx_lag, krx_days),
        # Evening refresh handles only this run's finalized session.  Historical
        # backfills and adjusted-price resyncs remain explicit manual jobs.
        kis=DateRange(start=kis_date, end=kis_date),
        kis_full_sync_symbol=None,
        ecos=window(ecos_lag, ecos_days),
        fred=window(fred_lag, fred_days),
    )


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class RunLog:
    """중단 시에도 마지막 완료 단계를 알 수 있는 원자적 실행 로그."""

    def __init__(
        self,
        plan: RefreshPlan,
        profile: str,
        root: Path = RUN_LOG_DIR,
    ):
        now = datetime.now(timezone.utc)
        self.run_id = f"{now:%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
        self.path = root / "runs" / f"{self.run_id}.json"
        self.latest_path = root / "latest.json"
        self.profile_latest_path = root / f"latest-{profile}.json"
        self.data = {
            "run_id": self.run_id,
            "profile": profile,
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
        _atomic_json(self.profile_latest_path, self.data)

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
    if name == "kis_market":
        prices = result.get("prices") or {}
        fundamentals = result.get("fundamentals") or {}
        full_resync = result.get("full_resync") or {}
        return bool(
            prices.get("failed_symbols")
            or fundamentals.get("failed_symbols")
            or full_resync.get("failed_symbols")
        )
    if name == "krx_stock_metadata":
        return bool(result.get("failed_dates"))
    if name == "krx_stock_master":
        return bool(result.get("failed_count"))
    if name in {"indices", "gold"}:
        return bool(result.get("failed") or result.get("empty_market"))
    return bool(result.get("failed"))


def default_steps(
    plan: RefreshPlan,
    request_interval: float,
    profile: str = "all",
    *,
    kis_symbols: Iterable[str] | None = None,
    kis_symbol_limit: int | None = None,
) -> list[tuple[str, Callable[[], dict]]]:
    """실행 시간대별 단계만 반환한다."""
    if profile not in {"morning", "evening", "all"}:
        raise ValueError(f"지원하지 않는 실행 프로필: {profile}")
    steps: list[tuple[str, Callable[[], dict]]] = []
    kis_enabled = _boolean_env("DAILY_REFRESH_KIS_ENABLED")
    if kis_enabled and profile in {"evening", "all"}:
        steps.append(
            (
                "kis_market",
                lambda: refresh_kis_market_data(
                    start_date=plan.kis.start,
                    end_date=plan.kis.end,
                    symbols=kis_symbols,
                    symbol_limit=kis_symbol_limit,
                    full_resync_symbol=plan.kis_full_sync_symbol,
                ),
            )
        )
    if profile not in {"morning", "all"}:
        return steps
    if kis_enabled:
        morning_context: dict[str, tuple[str, ...]] = {}
        master_date = _latest_krx_trading_day(plan.krx.end)

        def sync_stock_master() -> dict:
            try:
                existing = load_kospi_symbols()
            except ValueError:
                existing = ()
            result = sync_kospi_stocks(
                master_date,
                minimum_count=_positive_int_env(
                    "DAILY_REFRESH_KOSPI_MASTER_MIN_COUNT", 500
                ),
                existing_count=len(existing),
            )
            frozen = load_kospi_symbols()
            morning_context["symbols"] = frozen
            return {**result, "target_count": len(frozen)}

        def collect_stock_metadata() -> dict:
            return backfill_market_metadata(
                start_date=plan.krx.start,
                end_date=plan.krx.end,
                symbols=morning_context.get("symbols"),
                request_interval=request_interval,
            )

        steps.append(("krx_stock_master", sync_stock_master))
        steps.append(
            (
                "krx_stock_metadata",
                collect_stock_metadata,
            )
        )
    steps.extend([
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
    ])
    return steps


def run_refresh(
    plan: RefreshPlan,
    request_interval: float = 0.5,
    log_root: Path = RUN_LOG_DIR,
    steps: list[tuple[str, Callable[[], dict]]] | None = None,
    profile: str = "morning",
    kis_symbols: Iterable[str] | None = None,
    kis_symbol_limit: int | None = None,
) -> dict:
    """계획을 실행하고 단계별 결과 및 프로세스 종료 판단을 반환한다."""
    if request_interval < 0:
        raise ValueError("request_interval은 0 이상이어야 합니다.")

    if profile not in {"morning", "evening"}:
        raise ValueError(f"지원하지 않는 실행 프로필: {profile}")
    run_log = RunLog(plan, profile=profile, root=log_root)
    summary = {
        "run_id": run_log.run_id,
        "profile": profile,
        "status": "running",
        "steps": {},
    }

    try:
        with daily_refresh_lock() as acquired:
            if not acquired:
                summary["status"] = "skipped_concurrent"
                run_log.finish("skipped_concurrent")
                return summary

            has_failure = False
            for name, runner in steps or default_steps(
                plan,
                request_interval,
                profile=profile,
                kis_symbols=kis_symbols,
                kis_symbol_limit=kis_symbol_limit,
            ):
                try:
                    result = runner()
                    failed = _result_failed(name, result)
                    status = "failed" if failed else "success"
                except Exception as exc:
                    result = {
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                    if name == "krx_stock_master":
                        result["failed_count"] = 1
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
        "--profile",
        choices=("morning", "evening"),
        default="morning",
        help="morning=09:00 KRX·경제, evening=18:30 KIS",
    )
    parser.add_argument(
        "--print-plan",
        action="store_true",
        help="외부 API/DB를 호출하지 않고 날짜 계획만 출력",
    )
    parser.add_argument(
        "--kis-symbols",
        nargs="+",
        help="테스트·제한 실행용 KIS 종목코드 목록",
    )
    parser.add_argument(
        "--kis-symbol-limit",
        type=int,
        help="테스트·제한 실행용 KIS 최대 종목 수",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = datetime.now(SEOUL)
    if (
        args.profile == "evening"
        and args.as_of is None
        and now.time() < datetime_time(18, 30)
    ):
        print(json.dumps({
            "profile": "evening",
            "status": "skipped_before_18_30",
            "as_of": now.date().isoformat(),
        }, ensure_ascii=False, indent=2))
        return 0
    as_of = args.as_of or now.date()
    plan = build_refresh_plan(as_of)

    if args.print_plan:
        output = {
            "profile": args.profile,
            "plan": plan.to_dict(),
            "steps": [
                name
                for name, _ in default_steps(
                    plan,
                    args.request_interval,
                    profile=args.profile,
                    kis_symbols=args.kis_symbols,
                    kis_symbol_limit=args.kis_symbol_limit,
                )
            ],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    summary = run_refresh(
        plan,
        request_interval=args.request_interval,
        profile=args.profile,
        kis_symbols=args.kis_symbols,
        kis_symbol_limit=args.kis_symbol_limit,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 1 if summary["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
