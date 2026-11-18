from __future__ import annotations

from argparse import Namespace
from contextlib import contextmanager
from datetime import date, datetime, timezone

from scripts import (
    backfill_missing_market_metadata,
    collect_kis_fundamentals_snapshots,
    collect_kis_market_data,
    sync_kospi_stocks,
)


def test_two_stage_auto_requires_explicit_operational_enable(monkeypatch, capsys):
    monkeypatch.setattr(
        collect_kis_fundamentals_snapshots,
        "parse_args",
        lambda _argv=None: Namespace(command="capture-auto"),
    )
    monkeypatch.setattr(
        collect_kis_fundamentals_snapshots,
        "_two_stage_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        collect_kis_fundamentals_snapshots,
        "daily_refresh_lock",
        lambda: (_ for _ in ()).throw(AssertionError("lock must not run")),
    )

    assert collect_kis_fundamentals_snapshots.main() == 3
    assert '"status": "disabled"' in capsys.readouterr().out


def test_capture_auto_holiday_skips_before_target_or_api(monkeypatch, tmp_path):
    args = Namespace(
        symbols=None,
        symbol_limit=None,
        state_root=tmp_path,
    )
    monkeypatch.setattr(
        collect_kis_fundamentals_snapshots,
        "_targets",
        lambda _args: (_ for _ in ()).throw(
            AssertionError("holiday must not load targets")
        ),
    )

    result, status = collect_kis_fundamentals_snapshots._run_capture_auto(
        args,
        datetime(2026, 11, 8, 11, 0, tzinfo=timezone.utc),
    )

    assert status == 0
    assert result["status"] == "skipped_non_trading_day"


def test_finalize_auto_missing_capture_defers_without_api(monkeypatch, tmp_path):
    args = Namespace(
        symbols=("005930",),
        symbol_limit=None,
        state_root=tmp_path,
        recovery_days=10,
    )
    monkeypatch.setattr(
        collect_kis_fundamentals_snapshots,
        "_targets",
        lambda _args: (("005930",), ()),
    )
    monkeypatch.setattr(
        collect_kis_fundamentals_snapshots,
        "KisClient",
        lambda: (_ for _ in ()).throw(AssertionError("KIS API must not run")),
    )
    monkeypatch.setattr(
        collect_kis_fundamentals_snapshots,
        "fetch_kospi_daily",
        lambda _date: (_ for _ in ()).throw(AssertionError("KRX API must not run")),
    )

    result, status = collect_kis_fundamentals_snapshots._run_finalize_auto(
        args,
        datetime(2026, 11, 6, 0, 0, tzinfo=timezone.utc),
    )

    assert status == 1
    assert result["failed_dates"] == ["2026-11-05"]
    assert result["date_results"]["2026-11-05"]["status"] == "missing_capture"


def test_finalize_auto_never_processes_friday_session(monkeypatch, tmp_path):
    friday = date(2026, 11, 6)
    args = Namespace(
        symbols=None,
        symbol_limit=None,
        state_root=tmp_path,
        recovery_days=10,
        krx_warning_only=True,
    )
    monkeypatch.setattr(
        collect_kis_fundamentals_snapshots,
        "automatic_finalize_date",
        lambda _now: friday,
    )
    monkeypatch.setattr(
        collect_kis_fundamentals_snapshots,
        "pending_snapshot_dates",
        lambda *_args, **_kwargs: (friday,),
    )
    monkeypatch.setattr(
        collect_kis_fundamentals_snapshots,
        "capture_target_symbols",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("Friday must stay staged")
        ),
    )
    monkeypatch.setattr(
        collect_kis_fundamentals_snapshots,
        "KisClient",
        lambda: (_ for _ in ()).throw(AssertionError("KIS API must not run")),
    )

    result, status = collect_kis_fundamentals_snapshots._run_finalize_auto(
        args,
        datetime(2026, 11, 10, 23, 0, tzinfo=timezone.utc),
    )

    assert status == 0
    assert result["processed_dates"] == []
    assert result["failed_dates"] == []


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


def test_manual_backfill_never_calls_fundamentals_api(monkeypatch):
    @contextmanager
    def acquired_lock():
        yield True

    class Client:
        request_interval = 1.05
        rate_limit_cooldown = 61.0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def current_price(self, _symbol):
            raise AssertionError("과거 백필에서 투자지표 API를 호출하면 안 됩니다.")

        def request_metrics(self):
            return {
                "total": 0,
                "token": 0,
                "quotation": 0,
                "retries": 0,
                "rate_limit_errors": 0,
            }

    monkeypatch.setattr(collect_kis_market_data, "daily_refresh_lock", acquired_lock)
    monkeypatch.setattr(
        collect_kis_market_data,
        "parse_args",
        lambda: Namespace(
            start=date(2026, 10, 1),
            end=date(2026, 10, 28),
            symbols=("005930",),
            symbol_limit=None,
            no_resume=False,
            adjusted_only=False,
            krx_request_interval=0,
        ),
    )
    monkeypatch.setattr(
        collect_kis_market_data,
        "load_kospi_symbols",
        lambda **_kwargs: ("005930",),
    )
    monkeypatch.setattr(collect_kis_market_data, "assert_kis_schema", lambda: None)
    monkeypatch.setattr(collect_kis_market_data, "KisClient", Client)
    monkeypatch.setattr(
        collect_kis_market_data,
        "backfill_kis_prices",
        lambda *_args, **_kwargs: {"failed_symbols": []},
    )
    metadata_calls = []
    monkeypatch.setattr(
        collect_kis_market_data,
        "backfill_market_metadata",
        lambda *args, **kwargs: metadata_calls.append((args, kwargs)) or {
            "failed_dates": []
        },
    )

    assert collect_kis_market_data.main() == 0
    assert len(metadata_calls) == 1


def test_missing_metadata_backfill_discovers_only_existing_null_rows(monkeypatch):
    captured = {}

    class Rows:
        def mappings(self):
            return iter([
                {"trade_date": date(2023, 1, 2), "symbol": "034230"},
                {"trade_date": date(2023, 1, 2), "symbol": "066970"},
                {"trade_date": date(2023, 1, 3), "symbol": "034230"},
            ])

    class Connection:
        def execute(self, statement, params):
            captured["sql"] = str(statement)
            captured["params"] = params
            return Rows()

    class Connect:
        def __enter__(self):
            return Connection()

        def __exit__(self, *_args):
            return False

    class Engine:
        def connect(self):
            return Connect()

    monkeypatch.setattr(
        backfill_missing_market_metadata,
        "get_engine",
        lambda: Engine(),
    )

    result = backfill_missing_market_metadata.load_missing_keys(
        date(2023, 1, 1),
        date(2023, 1, 3),
        ("034230", "066970"),
    )

    assert result == {
        date(2023, 1, 2): ("034230", "066970"),
        date(2023, 1, 3): ("034230",),
    }
    assert "source = 'KIS'" in captured["sql"]
    assert "market_cap IS NULL" in captured["sql"]
