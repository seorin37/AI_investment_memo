from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime

import pytest

from pipelines import daily_refresh


def test_atomic_json_allows_concurrent_profiles(tmp_path):
    path = tmp_path / "latest.json"

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(
            lambda number: daily_refresh._atomic_json(path, {"number": number}),
            range(40),
        ))

    assert json.loads(path.read_text(encoding="utf-8"))["number"] in range(40)
    assert list(tmp_path.glob("*.tmp")) == []


def test_evening_timer_catchup_before_1830_does_not_collect(monkeypatch, capsys):
    class BeforeClose:
        @classmethod
        def now(cls, _timezone):
            return datetime(2026, 11, 2, 13, 19, tzinfo=daily_refresh.SEOUL)

    monkeypatch.setattr(daily_refresh, "datetime", BeforeClose)
    monkeypatch.setattr(
        daily_refresh,
        "run_refresh",
        lambda *_args, **_kwargs: pytest.fail("KIS refresh must not start"),
    )

    assert daily_refresh.main(["--profile", "evening"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "skipped_before_18_30"


def test_build_refresh_plan_uses_safe_lags_and_requery_windows(monkeypatch):
    for name in (
        "DAILY_REFRESH_KRX_LAG_DAYS",
        "DAILY_REFRESH_KIS_LAG_DAYS",
        "DAILY_REFRESH_ECOS_LAG_DAYS",
        "DAILY_REFRESH_FRED_LAG_DAYS",
        "DAILY_REFRESH_KRX_REQUERY_DAYS",
        "DAILY_REFRESH_ECOS_REQUERY_DAYS",
        "DAILY_REFRESH_FRED_REQUERY_DAYS",
    ):
        monkeypatch.delenv(name, raising=False)

    plan = daily_refresh.build_refresh_plan(date(2026, 10, 26))

    assert plan.krx.start == date(2026, 10, 19)
    assert plan.krx.end == date(2026, 10, 25)
    assert plan.kis.start == date(2026, 10, 26)
    assert plan.kis.end == date(2026, 10, 26)
    assert plan.kis_full_sync_symbol is None
    assert plan.ecos.start == date(2026, 9, 21)
    assert plan.ecos.end == date(2026, 10, 25)
    assert plan.fred == plan.ecos


def test_build_refresh_plan_allows_operational_overrides(monkeypatch):
    monkeypatch.setenv("DAILY_REFRESH_FRED_LAG_DAYS", "2")
    monkeypatch.setenv("DAILY_REFRESH_FRED_REQUERY_DAYS", "10")

    plan = daily_refresh.build_refresh_plan(date(2026, 10, 26))

    assert plan.fred.start == date(2026, 10, 15)
    assert plan.fred.end == date(2026, 10, 24)


def test_default_steps_requery_and_reuse_existing_pipelines(monkeypatch):
    calls = []
    monkeypatch.setenv("DAILY_REFRESH_KIS_ENABLED", "true")
    monkeypatch.setenv("DAILY_REFRESH_KOSPI_MASTER_MIN_COUNT", "1")

    def fake(name):
        def runner(**kwargs):
            calls.append((name, kwargs))
            return {"failed": []}
        return runner

    monkeypatch.setattr(daily_refresh, "refresh_kis_market_data", fake("kis_market"))
    monkeypatch.setattr(
        daily_refresh,
        "sync_kospi_stocks",
        lambda trade_date, **kwargs: calls.append(
            ("krx_stock_master", {"trade_date": trade_date, **kwargs})
        ) or {
            "received": 2, "inserted": 0, "updated": 0,
            "unchanged": 2, "failed_count": 0,
        },
    )
    monkeypatch.setattr(
        daily_refresh, "load_kospi_symbols", lambda: ("000660", "005930")
    )
    monkeypatch.setattr(
        daily_refresh, "backfill_market_metadata", fake("krx_stock_metadata")
    )
    monkeypatch.setattr(daily_refresh, "backfill_market_indices", fake("indices"))
    monkeypatch.setattr(daily_refresh, "backfill_gold_prices", fake("gold"))
    monkeypatch.setattr(daily_refresh, "backfill_ecos", fake("ecos"))
    monkeypatch.setattr(daily_refresh, "backfill_fred", fake("fred"))
    plan = daily_refresh.build_refresh_plan(date(2026, 10, 26))

    for _, runner in daily_refresh.default_steps(plan, request_interval=0):
        runner()

    assert [name for name, _ in calls] == [
        "kis_market", "krx_stock_master", "krx_stock_metadata",
        "indices", "gold", "ecos", "fred"
    ]
    assert calls[0][1]["start_date"] == plan.kis.start
    assert calls[0][1]["end_date"] == plan.kis.end
    assert calls[0][1]["full_resync_symbol"] is None
    assert calls[1][1]["trade_date"] == date(2026, 10, 23)
    assert calls[2][1]["start_date"] == plan.krx.start
    assert calls[2][1]["end_date"] == plan.krx.end
    assert calls[2][1]["symbols"] == ("000660", "005930")
    assert all(
        kwargs.get("resume") is False
        for name, kwargs in calls
        if name in {"indices", "gold", "ecos", "fred"}
    )


def test_daily_refresh_never_starts_historical_full_sync(monkeypatch):
    monkeypatch.setenv("DAILY_REFRESH_KIS_ENABLED", "true")
    plan = daily_refresh.build_refresh_plan(date(2026, 11, 1))

    assert plan.kis == daily_refresh.DateRange(
        start=date(2026, 10, 30), end=date(2026, 10, 30)
    )
    assert plan.kis_full_sync_symbol is None
    assert [name for name, _ in daily_refresh.default_steps(
        plan, 0, profile="evening"
    )] == ["kis_market"]


def test_kis_step_is_disabled_until_schema_is_approved(monkeypatch):
    monkeypatch.delenv("DAILY_REFRESH_KIS_ENABLED", raising=False)
    monkeypatch.setenv("DAILY_REFRESH_ADJUSTED_ENABLED", "true")
    plan = daily_refresh.build_refresh_plan(date(2026, 10, 26))

    assert [name for name, _ in daily_refresh.default_steps(plan, 0)] == [
        "indices",
        "gold",
        "ecos",
        "fred",
    ]


def test_metadata_deferred_rows_do_not_fail_other_refresh_steps():
    assert daily_refresh._result_failed(
        "krx_stock_metadata",
        {"failed_dates": [], "deferred_keys": ["005930:2026-10-28"]},
    ) is False
    assert daily_refresh._result_failed(
        "krx_stock_metadata",
        {"failed_dates": ["2026-10-28"], "deferred_keys": []},
    ) is True


def test_profiles_separate_morning_and_evening_steps(monkeypatch):
    monkeypatch.setenv("DAILY_REFRESH_KIS_ENABLED", "true")
    plan = daily_refresh.build_refresh_plan(date(2026, 10, 28))

    morning = [
        name
        for name, _ in daily_refresh.default_steps(plan, 0, profile="morning")
    ]
    evening = [
        name
        for name, _ in daily_refresh.default_steps(plan, 0, profile="evening")
    ]

    assert morning == [
        "krx_stock_master", "krx_stock_metadata",
        "indices", "gold", "ecos", "fred"
    ]
    assert evening == ["kis_market"]
    assert plan.krx.end == date(2026, 10, 27)
    assert plan.kis.end == date(2026, 10, 28)


def test_evening_profile_remains_empty_when_kis_is_disabled(monkeypatch):
    monkeypatch.delenv("DAILY_REFRESH_KIS_ENABLED", raising=False)
    plan = daily_refresh.build_refresh_plan(date(2026, 10, 28))

    assert daily_refresh.default_steps(plan, 0, profile="evening") == []


def test_evening_forwards_explicit_test_universe(monkeypatch):
    calls = []
    monkeypatch.setenv("DAILY_REFRESH_KIS_ENABLED", "true")
    monkeypatch.setattr(
        daily_refresh,
        "refresh_kis_market_data",
        lambda **kwargs: calls.append(kwargs) or {"failed_symbols": []},
    )
    plan = daily_refresh.build_refresh_plan(date(2026, 10, 28))
    steps = daily_refresh.default_steps(
        plan,
        0,
        profile="evening",
        kis_symbols=("005930", "000660"),
        kis_symbol_limit=1,
    )

    steps[0][1]()
    assert calls[0]["symbols"] == ("005930", "000660")
    assert calls[0]["symbol_limit"] == 1


def test_run_refresh_logs_partial_failure_and_continues(tmp_path, monkeypatch):
    @contextmanager
    def acquired_lock():
        yield True

    monkeypatch.setattr(daily_refresh, "daily_refresh_lock", acquired_lock)
    plan = daily_refresh.build_refresh_plan(date(2026, 10, 26))
    steps = [
        ("prices", lambda: {"failed_dates": [], "empty_dates": 0}),
        ("indices", lambda: {"failed": ["2026-10-24:KOSPI"], "empty_market": 0}),
        ("gold", lambda: {"failed": [], "empty_market": 0}),
    ]

    result = daily_refresh.run_refresh(
        plan,
        request_interval=0,
        log_root=tmp_path,
        steps=steps,
    )

    assert result["status"] == "failed"
    assert result["steps"]["gold"]["status"] == "success"
    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert latest["status"] == "failed"
    assert list(latest["steps"]) == ["prices", "indices", "gold"]
    assert (tmp_path / "runs" / f"{result['run_id']}.json").exists()


def test_master_failure_is_logged_and_other_morning_steps_continue(
    tmp_path, monkeypatch
):
    @contextmanager
    def acquired_lock():
        yield True

    called = []
    monkeypatch.setattr(daily_refresh, "daily_refresh_lock", acquired_lock)
    monkeypatch.setenv("DAILY_REFRESH_KIS_ENABLED", "true")
    monkeypatch.setenv("DAILY_REFRESH_KOSPI_MASTER_MIN_COUNT", "1")
    monkeypatch.setattr(
        daily_refresh, "load_kospi_symbols", lambda: ("005930",)
    )
    monkeypatch.setattr(
        daily_refresh,
        "sync_kospi_stocks",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("incomplete snapshot")
        ),
    )

    def fake(name):
        def runner(**_kwargs):
            called.append(name)
            if name in {"indices", "gold"}:
                return {"failed": [], "empty_market": 0}
            if name == "krx_stock_metadata":
                return {"failed_dates": [], "deferred_keys": []}
            return {"failed": []}
        return runner

    monkeypatch.setattr(
        daily_refresh, "backfill_market_metadata", fake("krx_stock_metadata")
    )
    monkeypatch.setattr(daily_refresh, "backfill_market_indices", fake("indices"))
    monkeypatch.setattr(daily_refresh, "backfill_gold_prices", fake("gold"))
    monkeypatch.setattr(daily_refresh, "backfill_ecos", fake("ecos"))
    monkeypatch.setattr(daily_refresh, "backfill_fred", fake("fred"))
    plan = daily_refresh.build_refresh_plan(date(2026, 10, 28))

    result = daily_refresh.run_refresh(
        plan,
        request_interval=0,
        log_root=tmp_path,
        profile="morning",
    )

    assert result["status"] == "failed"
    assert result["steps"]["krx_stock_master"]["result"]["failed_count"] == 1
    assert called == ["krx_stock_metadata", "indices", "gold", "ecos", "fred"]


def test_run_refresh_skips_when_another_worker_holds_lock(tmp_path, monkeypatch):
    @contextmanager
    def unavailable_lock():
        yield False

    called = False

    def runner():
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(daily_refresh, "daily_refresh_lock", unavailable_lock)
    plan = daily_refresh.build_refresh_plan(date(2026, 10, 26))

    result = daily_refresh.run_refresh(
        plan,
        request_interval=0,
        log_root=tmp_path,
        steps=[("prices", runner)],
    )

    assert result["status"] == "skipped_concurrent"
    assert called is False


@pytest.mark.parametrize("value", ["0", "-1", "not-a-number"])
def test_invalid_window_configuration_fails_fast(monkeypatch, value):
    monkeypatch.setenv("DAILY_REFRESH_KRX_REQUERY_DAYS", value)
    with pytest.raises(ValueError):
        daily_refresh.build_refresh_plan(date(2026, 10, 26))
