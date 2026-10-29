from __future__ import annotations

from argparse import Namespace
from contextlib import contextmanager
from datetime import date

from scripts import collect_kis_market_data, sync_kospi_stocks


def test_manual_stock_master_uses_full_snapshot_safety_defaults(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        sync_kospi_stocks,
        "parse_args",
        lambda: Namespace(
            trade_date=date(2026, 10, 28),
            minimum_count=500,
            minimum_existing_ratio=0.8,
        ),
    )
    monkeypatch.setattr(
        sync_kospi_stocks,
        "load_kospi_symbols",
        lambda: tuple(f"{number:06d}" for number in range(1, 901)),
    )

    def fake_sync(trade_date, **kwargs):
        captured.update(trade_date=trade_date, **kwargs)
        return {"received": 901, "failed_count": 0}

    monkeypatch.setattr(sync_kospi_stocks, "sync_kospi_stocks", fake_sync)

    assert sync_kospi_stocks.main() == 0
    assert captured == {
        "trade_date": date(2026, 10, 28),
        "minimum_count": 500,
        "existing_count": 900,
        "minimum_existing_ratio": 0.8,
    }


def test_manual_stock_master_allows_explicit_small_mock_threshold(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        sync_kospi_stocks,
        "parse_args",
        lambda: Namespace(
            trade_date=date(2026, 10, 28),
            minimum_count=2,
            minimum_existing_ratio=0.5,
        ),
    )
    monkeypatch.setattr(
        sync_kospi_stocks, "load_kospi_symbols", lambda: ("005930", "000660")
    )
    monkeypatch.setattr(
        sync_kospi_stocks,
        "sync_kospi_stocks",
        lambda trade_date, **kwargs: captured.update(
            trade_date=trade_date, **kwargs
        ) or {"received": 2, "failed_count": 0},
    )

    assert sync_kospi_stocks.main() == 0
    assert captured["minimum_count"] == 2
    assert captured["minimum_existing_ratio"] == 0.5


def test_manual_backfill_stops_before_target_or_api_when_lock_is_busy(
    monkeypatch,
):
    @contextmanager
    def busy_lock():
        yield False

    monkeypatch.setattr(collect_kis_market_data, "daily_refresh_lock", busy_lock)
    monkeypatch.setattr(
        collect_kis_market_data,
        "parse_args",
        lambda: Namespace(
            start=date(2026, 10, 28),
            end=date(2026, 10, 28),
            symbols=None,
            symbol_limit=None,
            no_resume=False,
            adjusted_only=False,
            krx_request_interval=0,
        ),
    )
    monkeypatch.setattr(
        collect_kis_market_data,
        "load_kospi_symbols",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("target lookup must not run")
        ),
    )

    assert collect_kis_market_data.main() == 2
