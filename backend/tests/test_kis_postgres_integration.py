"""KIS PostgreSQL integration tests for an explicitly isolated database only."""

from __future__ import annotations

from argparse import Namespace
import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from pipelines.market import kis, metadata
from pipelines import daily_refresh
from scripts import collect_kis_market_data


TEST_URL_ENV = "KIS_INTEGRATION_DATABASE_URL"


def _isolated_url() -> str:
    raw = os.environ.get(TEST_URL_ENV)
    if not raw:
        pytest.skip(f"{TEST_URL_ENV} is not set")
    url = make_url(raw)
    database = url.database or ""
    if (
        url.host not in {"127.0.0.1", "localhost"}
        or url.port in {None, 5432}
        or not database.startswith("memos_kis_it_")
    ):
        pytest.fail("KIS integration database is not an isolated local test database")
    return raw


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(_isolated_url(), pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO stocks (symbol, name)
                VALUES
                  ('005930', 'Samsung Electronics'),
                  ('000660', 'SK hynix'),
                  ('035420', 'NAVER'),
                  ('105560', 'KB Financial')
                ON CONFLICT (symbol) DO NOTHING
                """
            )
        )
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def use_isolated_engine(monkeypatch, pg_engine):
    monkeypatch.setattr(kis, "get_engine", lambda: pg_engine)
    monkeypatch.setattr(metadata, "get_engine", lambda: pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                """
                DELETE FROM stock_fundamentals_snapshot
                WHERE symbol IN ('005930', '000660', '035420', '105560');
                DELETE FROM adjusted_prices_daily
                WHERE symbol IN ('005930', '000660', '035420', '105560');
                DELETE FROM prices_daily
                WHERE symbol IN ('005930', '000660', '035420', '105560')
                """
            )
        )


def _price_rows(symbol: str, trade_date: date):
    collected_at = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    common = {
        "symbol": symbol,
        "trade_date": trade_date,
        "open": Decimal("100"),
        "high": Decimal("120"),
        "low": Decimal("90"),
        "close": Decimal("110"),
        "volume": 700,
        "source": "KIS",
    }
    raw = {
        **common,
        "trade_value": Decimal("77000"),
        "market_cap": None,
        "listed_shares": None,
        "market_metadata_source": None,
        "collected_at": collected_at,
    }
    adjusted = {
        **common,
        "adjustment_basis": kis.ADJUSTMENT_BASIS,
        "collected_at": collected_at,
    }
    return raw, adjusted


def _fundamental_row(symbol: str, trade_date: date):
    return {
        "symbol": symbol,
        "basis_trade_date": trade_date,
        "per": Decimal("10.5"),
        "pbr": Decimal("1.2"),
        "eps": Decimal("10.4762"),
        "bps": Decimal("91.6667"),
        "w52_high": Decimal("130"),
        "w52_high_date": date(2026, 9, 1),
        "w52_low": Decimal("70"),
        "w52_low_date": date(2025, 11, 1),
        "market_cap": Decimal("110000000"),
        "listed_shares": 1_000_000,
        "reference_price": Decimal("110"),
        "final_close": Decimal("110"),
        "source": "KIS",
        "collected_at": datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc),
    }


def test_schema_is_at_0011_with_required_constraints(pg_engine):
    with pg_engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        constraints = set(
            connection.execute(
                text(
                    """
                    SELECT conname
                    FROM pg_constraint
                    WHERE conrelid IN (
                      'prices_daily'::regclass,
                      'adjusted_prices_daily'::regclass,
                      'stock_fundamentals_snapshot'::regclass
                    )
                    """
                )
            ).scalars()
        )
        not_null_columns = set(
            connection.execute(
                text(
                    """
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name IN (
                        'prices_daily',
                        'adjusted_prices_daily',
                        'stock_fundamentals_snapshot'
                      )
                      AND is_nullable = 'NO'
                    """
                )
            )
        )
    assert revision == "0011_kis_market_data"
    assert {
        "prices_daily_pkey",
        "adjusted_prices_daily_pkey",
        "adjusted_prices_daily_symbol_fkey",
        "ck_adjusted_prices_daily_positive_ohlc",
        "ck_adjusted_prices_daily_volume",
        "stock_fundamentals_snapshot_pkey",
        "stock_fundamentals_snapshot_symbol_fkey",
        "ck_stock_fundamentals_snapshot_final_close",
    } <= constraints
    assert {
        ("prices_daily", "symbol"),
        ("prices_daily", "trade_date"),
        ("prices_daily", "open"),
        ("prices_daily", "high"),
        ("prices_daily", "low"),
        ("prices_daily", "close"),
        ("prices_daily", "volume"),
        ("prices_daily", "source"),
        ("adjusted_prices_daily", "symbol"),
        ("adjusted_prices_daily", "trade_date"),
        ("adjusted_prices_daily", "source"),
        ("adjusted_prices_daily", "adjustment_basis"),
        ("stock_fundamentals_snapshot", "symbol"),
        ("stock_fundamentals_snapshot", "basis_trade_date"),
        ("stock_fundamentals_snapshot", "final_close"),
        ("stock_fundamentals_snapshot", "source"),
    } <= not_null_columns


def test_prices_fundamentals_and_metadata_upsert_idempotently(pg_engine):
    trade_date = date(2026, 10, 27)
    raw, adjusted = _price_rows("005930", trade_date)
    fundamental = _fundamental_row("005930", trade_date)

    assert kis.save_kis_prices([raw], [adjusted]) == 2
    assert kis.save_fundamentals([fundamental]) == 1
    assert kis.save_kis_prices([raw], [adjusted]) == 2
    assert kis.save_fundamentals([fundamental]) == 1
    latest = kis.load_latest_raw_prices(
        ("005930", "000660"), trade_date, trade_date
    )
    assert latest == {
        "005930": {
            "symbol": "005930",
            "trade_date": trade_date,
            "close": Decimal("110.00"),
        }
    }

    update = metadata.save_market_metadata(
        [
            {
                "symbol": "005930",
                "trade_date": trade_date,
                "market_cap": Decimal("123456789"),
                "listed_shares": 987654,
                "market_metadata_source": "KRX_OPEN_API",
            },
            {
                "symbol": "000660",
                "trade_date": trade_date,
                "market_cap": Decimal("1"),
                "listed_shares": 1,
                "market_metadata_source": "KRX_OPEN_API",
            },
        ]
    )
    assert update == {
        "updated_rows": 1,
        "deferred_keys": ["000660:2026-10-27"],
    }

    with pg_engine.connect() as connection:
        counts = connection.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM prices_daily
                   WHERE symbol = '005930' AND trade_date = :day),
                  (SELECT count(*) FROM adjusted_prices_daily
                   WHERE symbol = '005930' AND trade_date = :day),
                  (SELECT count(*) FROM stock_fundamentals_snapshot
                   WHERE symbol = '005930' AND basis_trade_date = :day)
                """
            ),
            {"day": trade_date},
        ).one()
        raw_saved = connection.execute(
            text(
                """
                SELECT open, high, low, close, volume, trade_value,
                       market_cap, listed_shares, source, market_metadata_source
                FROM prices_daily
                WHERE symbol = '005930' AND trade_date = :day
                """
            ),
            {"day": trade_date},
        ).mappings().one()
        adjusted_saved = connection.execute(
            text(
                """
                SELECT close, volume, source, adjustment_basis
                FROM adjusted_prices_daily
                WHERE symbol = '005930' AND trade_date = :day
                """
            ),
            {"day": trade_date},
        ).mappings().one()
        fundamental_saved = connection.execute(
            text(
                """
                SELECT per, pbr, eps, bps, w52_high, w52_low,
                       reference_price, final_close, source
                FROM stock_fundamentals_snapshot
                WHERE symbol = '005930' AND basis_trade_date = :day
                """
            ),
            {"day": trade_date},
        ).mappings().one()

    assert tuple(counts) == (1, 1, 1)
    assert raw_saved["close"] == Decimal("110.00")
    assert raw_saved["market_cap"] == Decimal("123456789")
    assert raw_saved["listed_shares"] == 987654
    assert raw_saved["source"] == "KIS"
    assert raw_saved["market_metadata_source"] == "KRX_OPEN_API"
    assert adjusted_saved["volume"] == 700
    assert adjusted_saved["adjustment_basis"] == kis.ADJUSTMENT_BASIS
    assert fundamental_saved["per"] == Decimal("10.500000")
    assert fundamental_saved["eps"] == Decimal("10.4762")
    assert fundamental_saved["source"] == "KIS"


def test_metadata_uses_database_source_and_preserves_non_kis_ohlcv(pg_engine):
    trade_date = date(2026, 10, 24)
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO prices_daily (
                  symbol, trade_date, open, high, low, close, volume, source
                ) VALUES (
                  '000660', :day, 10, 12, 9, 11, 123, 'KRX_OPEN_API'
                )
                """
            ),
            {"day": trade_date},
        )

    result = metadata.save_market_metadata(
        [{
            "symbol": "000660",
            "trade_date": trade_date,
            "market_cap": Decimal("999999"),
            "listed_shares": 12345,
            "market_metadata_source": "KRX_OPEN_API",
        }]
    )

    assert result == {
        "updated_rows": 0,
        "deferred_keys": ["000660:2026-10-24"],
    }
    with pg_engine.connect() as connection:
        saved = connection.execute(
            text(
                """
                SELECT open, high, low, close, volume, source,
                       market_cap, listed_shares, market_metadata_source
                FROM prices_daily
                WHERE symbol = '000660' AND trade_date = :day
                """
            ),
            {"day": trade_date},
        ).mappings().one()
    assert tuple(saved[key] for key in ("open", "high", "low", "close")) == (
        Decimal("10.00"), Decimal("12.00"), Decimal("9.00"), Decimal("11.00")
    )
    assert saved["volume"] == 123
    assert saved["source"] == "KRX_OPEN_API"
    assert saved["market_cap"] is None
    assert saved["listed_shares"] is None
    assert saved["market_metadata_source"] is None


def test_price_pair_rolls_back_when_adjusted_insert_fails(pg_engine):
    trade_date = date(2026, 10, 26)
    raw, adjusted = _price_rows("000660", trade_date)
    adjusted["volume"] = -1

    with pytest.raises(IntegrityError):
        kis.save_kis_prices([raw], [adjusted])

    with pg_engine.connect() as connection:
        counts = connection.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM prices_daily
                   WHERE symbol = '000660' AND trade_date = :day),
                  (SELECT count(*) FROM adjusted_prices_daily
                   WHERE symbol = '000660' AND trade_date = :day)
                """
            ),
            {"day": trade_date},
        ).one()
    assert tuple(counts) == (0, 0)


def test_failed_side_checkpoint_matches_postgres_and_resumes(
    monkeypatch, tmp_path, pg_engine
):
    trade_date = date(2026, 10, 28)
    raw, adjusted = _price_rows("035420", trade_date)
    fail_adjusted = True

    def fake_fetch(_client, _symbol, _start, _end, *, adjusted: bool):
        nonlocal fail_adjusted
        if adjusted and fail_adjusted:
            raise kis.KisApiError("mock adjusted failure")
        return ([dict(adjusted_row)] if adjusted else [dict(raw)]), 0

    adjusted_row = adjusted
    monkeypatch.setattr(kis, "fetch_daily_range", fake_fetch)
    first = kis.backfill_kis_prices(
        trade_date,
        trade_date,
        ("035420",),
        client=object(),
        resume=True,
        state_root=tmp_path,
    )
    with pg_engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT count(*) FROM prices_daily WHERE symbol = '035420' AND trade_date = :day"
            ),
            {"day": trade_date},
        ).scalar_one() == 0
    failures = json.loads(
        (tmp_path / "kis_prices_failed.json").read_text(encoding="utf-8")
    )
    assert first["remaining_failures"] == 1
    assert next(iter(failures.values()))["status"] == "failed"

    fail_adjusted = False
    second = kis.backfill_kis_prices(
        trade_date,
        trade_date,
        ("035420",),
        client=object(),
        resume=True,
        state_root=tmp_path,
    )
    with pg_engine.connect() as connection:
        counts = connection.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM prices_daily
                   WHERE symbol = '035420' AND trade_date = :day),
                  (SELECT count(*) FROM adjusted_prices_daily
                   WHERE symbol = '035420' AND trade_date = :day)
                """
            ),
            {"day": trade_date},
        ).one()
    assert tuple(counts) == (1, 1)
    assert second["completed_symbols"] == ["035420"]
    assert second["remaining_failures"] == 0


def test_database_constraints_reject_invalid_rows(pg_engine):
    with pytest.raises(IntegrityError):
        with pg_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO prices_daily (
                      symbol, trade_date, open, high, low, close, source
                    ) VALUES (
                      '105560', '2026-10-25', 1, 1, 1, 1, 'KIS'
                    )
                    """
                )
            )

    with pytest.raises(IntegrityError):
        with pg_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO stock_fundamentals_snapshot (
                      symbol, basis_trade_date, final_close, source
                    ) VALUES ('105560', '2026-10-25', 0, 'KIS')
                    """
                )
            )

    with pytest.raises(IntegrityError):
        with pg_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO adjusted_prices_daily (
                      symbol, trade_date, open, high, low, close, volume,
                      source, adjustment_basis
                    ) VALUES (
                      '999999', '2026-10-25', 1, 1, 1, 1, 1,
                      'KIS', 'test'
                    )
                    """
                )
            )


def test_morning_evening_advisory_lock_prevents_overlap(monkeypatch):
    monkeypatch.setattr(daily_refresh, "database_url", _isolated_url)

    with daily_refresh.daily_refresh_lock() as evening_acquired:
        assert evening_acquired is True
        with daily_refresh.daily_refresh_lock() as morning_acquired:
            assert morning_acquired is False
    with daily_refresh.daily_refresh_lock() as later_morning:
        assert later_morning is True


def test_manual_backfill_uses_same_postgres_advisory_lock(monkeypatch):
    monkeypatch.setattr(daily_refresh, "database_url", _isolated_url)
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
            AssertionError("manual collection must not start")
        ),
    )

    with daily_refresh.daily_refresh_lock() as acquired:
        assert acquired is True
        assert collect_kis_market_data.main() == 2
