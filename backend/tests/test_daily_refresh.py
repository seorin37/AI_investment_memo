from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date

import pytest

from pipelines import daily_refresh


def test_build_refresh_plan_uses_safe_lags_and_requery_windows(monkeypatch):
    for name in (
        "DAILY_REFRESH_KRX_LAG_DAYS",
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

    def fake(name):
        def runner(**kwargs):
            calls.append((name, kwargs))
            return {"failed": []}
        return runner

    monkeypatch.setattr(daily_refresh, "backfill_prices", fake("prices"))
    monkeypatch.setattr(daily_refresh, "backfill_market_indices", fake("indices"))
    monkeypatch.setattr(daily_refresh, "backfill_gold_prices", fake("gold"))
    monkeypatch.setattr(daily_refresh, "backfill_ecos", fake("ecos"))
    monkeypatch.setattr(daily_refresh, "backfill_fred", fake("fred"))
    plan = daily_refresh.build_refresh_plan(date(2026, 10, 26))

    for _, runner in daily_refresh.default_steps(plan, request_interval=0):
        runner()

    assert [name for name, _ in calls] == [
        "prices", "indices", "gold", "ecos", "fred"
    ]
    assert all(kwargs["resume"] is False for _, kwargs in calls)
    assert calls[0][1]["symbols"] == daily_refresh.TEST_SYMBOLS
    assert calls[0][1]["scope"] == "test"


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
