"""End-to-end market pipeline tests against an explicitly isolated PostgreSQL."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from pipelines import daily_refresh
from pipelines.market import kis, metadata, stock_master


TEST_URL_ENV = "MARKET_PIPELINE_E2E_DATABASE_URL"


def _isolated_url() -> str:
    raw = os.environ.get(TEST_URL_ENV)
    if not raw:
        pytest.skip(f"{TEST_URL_ENV} is not set")
    url = make_url(raw)
    database = (url.database or "").lower()
    if (
        url.host not in {"127.0.0.1", "localhost"}
        or url.port in {None, 5432}
        or not database.startswith("memos_market_e2e_test_")
    ):
        pytest.fail("market E2E database is not an isolated local test database")
    return raw


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(_isolated_url(), pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch, pg_engine):
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE stock_fundamentals_snapshot,
                         adjusted_prices_daily, prices_daily, stocks CASCADE
                """
            )
        )
    monkeypatch.setattr(kis, "get_engine", lambda: pg_engine)
    monkeypatch.setattr(metadata, "get_engine", lambda: pg_engine)
    monkeypatch.setattr(stock_master, "get_engine", lambda: pg_engine)


def _master_row(symbol: str, name: str) -> dict:
    return {
        "ISU_CD": f"KR7{symbol}003",
        "ISU_SRT_CD": symbol,
        "ISU_NM": f"{name} 보통주",
        "ISU_ABBRV": name,
        "MKT_TP_NM": "KOSPI",
    }


def _sync_master(pg_engine, rows: list[dict]) -> dict:
    return stock_master.sync_kospi_stocks(
        date(2026, 10, 28),
        fetcher=lambda _day: rows,
        saver=lambda values: stock_master.save_kospi_stocks(
            values, engine=pg_engine
        ),
    )


def _daily_row(symbol: str, trade_date: date) -> dict[str, str]:
    base = 100 + int(symbol[-1])
    return {
        "stck_bsop_date": trade_date.strftime("%Y%m%d"),
        "stck_oprc": str(base),
        "stck_hgpr": str(base + 5),
        "stck_lwpr": str(base - 5),
        "stck_clpr": str(base + 2),
        "acml_vol": str(1000 + int(symbol[-1])),
        "acml_tr_pbmn": str((base + 2) * 1000),
    }


class MockKisClient:
    def __init__(self, trade_date: date, failed_symbols=()):
        self.trade_date = trade_date
        self.failed_symbols = set(failed_symbols)
        self.calls: list[tuple[str, object]] = []

    def daily_page(self, symbol, _start, _end, *, adjusted):
        self.calls.append((symbol, adjusted))
        if symbol in self.failed_symbols:
            raise kis.KisApiError("mock symbol failure")
        return [_daily_row(symbol, self.trade_date)]

    def current_price(self, symbol):
        self.calls.append((symbol, "fundamentals"))
        close = 102 + int(symbol[-1])
        return {
            "per": "10.5",
            "pbr": "1.2",
            "eps": "9.7143",
            "bps": "85",
            "w52_hgpr": "150",
            "w52_hgpr_date": "20261001",
            "w52_lwpr": "70",
            "w52_lwpr_date": "20251103",
            "hts_avls": "10",
            "lstn_stcn": "1000000",
            "stck_prpr": str(close),
            "acml_vol": "0",
        }


def _metadata_rows(symbols, trade_date):
    return [
        {
            "MKT_NM": "KOSPI",
            "ISU_CD": symbol,
            "BAS_DD": trade_date.strftime("%Y%m%d"),
            "MKTCAP": str(1_000_000_000 + index),
            "LIST_SHRS": str(1_000_000 + index),
        }
        for index, symbol in enumerate(symbols)
    ]


def test_full_pipeline_defers_recovers_and_is_idempotent(pg_engine, tmp_path):
    trade_date = date(2026, 10, 28)
    master = [
        _master_row("910001", "통합일"),
        _master_row("910002", "통합이"),
        _master_row("910003", "통합삼"),
    ]
    first_master = _sync_master(pg_engine, master)
    targets = stock_master.load_kospi_symbols(engine=pg_engine)
    assert first_master["inserted"] == 3
    assert targets == ("910001", "910002", "910003")

    krx_rows = _metadata_rows(targets, trade_date)
    morning_first = metadata.backfill_market_metadata(
        trade_date,
        trade_date,
        symbols=targets,
        request_interval=0,
        fetcher=lambda _day: krx_rows,
        check_schema=False,
    )
    assert morning_first["updated_count"] == 0
    assert morning_first["deferred_count"] == 3

    state_root = tmp_path / "daily" / trade_date.isoformat()
    client = MockKisClient(trade_date, failed_symbols={"910003"})
    first_prices = kis.backfill_kis_prices(
        trade_date,
        trade_date,
        targets,
        client=client,
        resume=True,
        state_root=state_root,
    )
    assert first_prices["completed_count"] == 2
    assert first_prices["failed_symbols"] == ["910003"]

    latest = kis.load_latest_raw_prices(targets, trade_date, trade_date)
    first_fundamentals = kis.collect_fundamentals(
        client,
        targets,
        latest,
        collected_at=datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc),
    )
    assert first_fundamentals["saved_rows"] == 2
    assert first_fundamentals["failed_symbols"] == ["910003"]

    morning_partial = metadata.backfill_market_metadata(
        trade_date,
        trade_date,
        symbols=targets,
        request_interval=0,
        fetcher=lambda _day: krx_rows,
        check_schema=False,
    )
    assert morning_partial["updated_count"] == 2
    assert morning_partial["deferred_keys"] == ["910003:2026-10-28"]

    client.failed_symbols.clear()
    recovered = kis.backfill_kis_prices(
        trade_date,
        trade_date,
        targets,
        client=client,
        resume=True,
        state_root=state_root,
    )
    assert recovered["skipped_count"] == 2
    assert recovered["failed_count"] == 0
    assert recovered["completed_count"] == 3
    latest = kis.load_latest_raw_prices(targets, trade_date, trade_date)
    recovered_fundamentals = kis.collect_fundamentals(
        client,
        targets,
        latest,
        collected_at=datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc),
    )
    assert recovered_fundamentals["saved_rows"] == 3
    assert recovered_fundamentals["failed_symbols"] == []

    morning_recovered = metadata.backfill_market_metadata(
        trade_date,
        trade_date,
        symbols=targets,
        request_interval=0,
        fetcher=lambda _day: krx_rows,
        check_schema=False,
    )
    assert morning_recovered["updated_count"] == 1
    assert morning_recovered["deferred_count"] == 0

    with pg_engine.connect() as connection:
        counts = connection.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM stocks),
                  (SELECT count(*) FROM prices_daily),
                  (SELECT count(*) FROM adjusted_prices_daily),
                  (SELECT count(*) FROM stock_fundamentals_snapshot)
                """
            )
        ).one()
        rows = connection.execute(
            text(
                """
                SELECT p.symbol, p.trade_date, p.source,
                       p.close, p.market_cap, p.listed_shares,
                       p.market_metadata_source,
                       a.source AS adjusted_source,
                       f.per, f.pbr, f.eps, f.bps,
                       f.w52_high, f.w52_low, f.source AS fundamental_source
                FROM prices_daily p
                JOIN adjusted_prices_daily a USING (symbol, trade_date)
                JOIN stock_fundamentals_snapshot f
                  ON f.symbol = p.symbol
                 AND f.basis_trade_date = p.trade_date
                ORDER BY p.symbol
                """
            )
        ).mappings().all()
    assert tuple(counts) == (3, 3, 3, 3)
    assert [row["symbol"] for row in rows] == list(targets)
    assert all(row["trade_date"] == trade_date for row in rows)
    assert all(row["source"] == "KIS" for row in rows)
    assert all(row["adjusted_source"] == "KIS" for row in rows)
    assert all(row["fundamental_source"] == "KIS" for row in rows)
    assert all(row["market_metadata_source"] == "KRX_OPEN_API" for row in rows)
    assert all(row["market_cap"] is not None for row in rows)
    assert all(row["per"] == Decimal("10.500000") for row in rows)
    assert all(row["w52_high"] == Decimal("150.00") for row in rows)

    same_prices = kis.backfill_kis_prices(
        trade_date,
        trade_date,
        targets,
        client=client,
        resume=True,
        state_root=state_root,
    )
    same_metadata = metadata.backfill_market_metadata(
        trade_date,
        trade_date,
        symbols=targets,
        request_interval=0,
        fetcher=lambda _day: krx_rows,
        check_schema=False,
    )
    assert same_prices["skipped_count"] == 3
    assert same_prices["raw_rows"] == same_prices["adjusted_rows"] == 0
    assert same_metadata["updated_count"] == 0
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM prices_daily")).scalar_one() == 3

    next_master = master + [_master_row("910004", "통합신규")]
    master_update = _sync_master(pg_engine, next_master)
    assert master_update["inserted"] == 1
    assert stock_master.load_kospi_symbols(engine=pg_engine) == (
        "910001", "910002", "910003", "910004"
    )


def test_corrupt_or_deleted_checkpoint_replays_upsert_safely(pg_engine, tmp_path):
    trade_date = date(2026, 10, 27)
    _sync_master(pg_engine, [_master_row("920001", "체크포인트")])
    state_root = tmp_path / "manual"
    client = MockKisClient(trade_date)

    kis.backfill_kis_prices(
        trade_date, trade_date, ("920001",), client=client,
        state_root=state_root, resume=True,
    )
    completed = state_root / "kis_prices_completed.json"
    completed.write_text("{broken", encoding="utf-8")
    replayed = kis.backfill_kis_prices(
        trade_date, trade_date, ("920001",), client=client,
        state_root=state_root, resume=True,
    )
    assert replayed["completed_count"] == 1
    assert len(list(state_root.glob("kis_prices_completed.json.corrupt-*"))) == 1

    completed.unlink()
    deleted_replay = kis.backfill_kis_prices(
        trade_date, trade_date, ("920001",), client=client,
        state_root=state_root, resume=True,
    )
    assert deleted_replay["completed_count"] == 1
    with pg_engine.connect() as connection:
        counts = connection.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM prices_daily),
                  (SELECT count(*) FROM adjusted_prices_daily)
                """
            )
        ).one()
    assert tuple(counts) == (1, 1)


def test_empty_database_guard_and_manual_daily_independence(
    monkeypatch, pg_engine, tmp_path
):
    constructed = False

    class ForbiddenClient:
        def __init__(self):
            nonlocal constructed
            constructed = True

    monkeypatch.setattr(kis, "KisClient", ForbiddenClient)
    with pytest.raises(ValueError, match="종목 마스터"):
        kis.refresh_kis_market_data(
            date(2026, 10, 28), date(2026, 10, 28)
        )
    assert constructed is False

    _sync_master(pg_engine, [_master_row("930001", "독립실행")])
    manual_date = date(2026, 10, 27)
    daily_date = date(2026, 10, 28)
    manual = kis.backfill_kis_prices(
        manual_date,
        manual_date,
        ("930001",),
        client=MockKisClient(manual_date),
        state_root=tmp_path / "manual-backfill",
    )
    daily = kis.backfill_kis_prices(
        daily_date,
        daily_date,
        ("930001",),
        client=MockKisClient(daily_date),
        state_root=tmp_path / "daily" / daily_date.isoformat(),
    )
    assert manual["completed_count"] == daily["completed_count"] == 1
    assert (tmp_path / "manual-backfill" / "kis_prices_completed.json").exists()
    assert (
        tmp_path / "daily" / daily_date.isoformat()
        / "kis_prices_completed.json"
    ).exists()
    with pg_engine.connect() as connection:
        dates = connection.execute(
            text("SELECT trade_date FROM prices_daily ORDER BY trade_date")
        ).scalars().all()
    assert dates == [manual_date, daily_date]


def test_morning_syncs_latest_master_first_and_freezes_metadata_targets(
    monkeypatch, pg_engine
):
    snapshot = [
        _master_row("940001", "모닝일"),
        _master_row("940002", "모닝이"),
        _master_row("940003", "모닝삼"),
    ]
    master_dates = []
    metadata_targets = []

    def sync_wrapper(trade_date, **kwargs):
        master_dates.append(trade_date)
        return stock_master.sync_kospi_stocks(
            trade_date,
            fetcher=lambda _day: list(snapshot),
            saver=lambda rows: stock_master.save_kospi_stocks(
                rows, engine=pg_engine
            ),
            **kwargs,
        )

    def metadata_wrapper(**kwargs):
        metadata_targets.append(tuple(kwargs["symbols"]))
        return {
            "failed_dates": [], "deferred_keys": [],
            "target_count": len(kwargs["symbols"]),
        }

    monkeypatch.setenv("DAILY_REFRESH_KIS_ENABLED", "true")
    monkeypatch.setenv("DAILY_REFRESH_KOSPI_MASTER_MIN_COUNT", "3")
    monkeypatch.setattr(daily_refresh, "sync_kospi_stocks", sync_wrapper)
    monkeypatch.setattr(
        daily_refresh,
        "load_kospi_symbols",
        lambda: stock_master.load_kospi_symbols(engine=pg_engine),
    )
    monkeypatch.setattr(
        daily_refresh, "backfill_market_metadata", metadata_wrapper
    )
    plan = daily_refresh.build_refresh_plan(date(2026, 11, 1))
    steps = daily_refresh.default_steps(plan, 0, profile="morning")

    first_master = steps[0][1]()
    first_metadata = steps[1][1]()
    assert master_dates == [date(2026, 10, 30)]
    assert first_master["inserted"] == 3
    assert first_master["target_count"] == 3
    assert first_metadata["target_count"] == 3
    assert metadata_targets[-1] == ("940001", "940002", "940003")

    with pg_engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE stocks
                SET sector = 'financial', dart_corp_code = '12345678'
                WHERE symbol = '940001'
                """
            )
        )

    incomplete = list(snapshot[:1])
    snapshot[:] = incomplete
    retry_steps = daily_refresh.default_steps(plan, 0, profile="morning")
    with pytest.raises(ValueError, match="명백히 불완전"):
        retry_steps[0][1]()
    with pg_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM stocks")).scalar_one() == 3

    snapshot[:] = [
        _master_row("940001", "모닝일변경"),
        _master_row("940002", "모닝이"),
        _master_row("940003", "모닝삼"),
        _master_row("940004", "모닝신규"),
    ]
    final_steps = daily_refresh.default_steps(plan, 0, profile="morning")
    final_master = final_steps[0][1]()
    final_steps[1][1]()
    assert final_master["inserted"] == 1
    assert final_master["updated"] == 1
    assert final_master["unchanged"] == 2
    assert metadata_targets[-1] == (
        "940001", "940002", "940003", "940004"
    )
    with pg_engine.connect() as connection:
        preserved = connection.execute(
            text(
                """
                SELECT name, sector::text, dart_corp_code
                FROM stocks WHERE symbol = '940001'
                """
            )
        ).one()
    assert preserved == ("모닝일변경", "financial", "12345678")
