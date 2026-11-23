"""Friday pipeline DB tests for an explicitly isolated local PostgreSQL only."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from pipelines.market import friday


ENV = "FRIDAY_PIPELINE_INTEGRATION_DATABASE_URL"
SYMBOL = "999980"
DAY = date(2026, 11, 20)


def _url() -> str:
    raw = os.environ.get(ENV)
    if not raw:
        pytest.skip(f"{ENV} is not set")
    url = make_url(raw)
    database = (url.database or "").lower()
    if (
        url.host not in {"127.0.0.1", "localhost"}
        or url.port in {None, 5432}
        or not database.startswith("memos_friday_test_")
    ):
        pytest.fail("금요일 파이프라인 격리 테스트 DB가 아닙니다.")
    for name in ("DATABASE_URL", "READONLY_DATABASE_URL"):
        other = os.environ.get(name)
        if other:
            parsed = make_url(other)
            if (parsed.host, parsed.port, parsed.database) == (url.host, url.port, url.database):
                pytest.fail(f"격리 테스트 DB가 {name}과 같습니다.")
    return raw


@pytest.fixture()
def engine():
    db = create_engine(_url(), pool_pre_ping=True)
    friday.assert_friday_schema(engine=db)
    with db.begin() as connection:
        connection.execute(text("DELETE FROM stock_fundamentals_snapshot WHERE symbol=:s"), {"s": SYMBOL})
        connection.execute(text("DELETE FROM adjusted_prices_daily WHERE symbol=:s"), {"s": SYMBOL})
        connection.execute(text("DELETE FROM prices_daily WHERE symbol=:s"), {"s": SYMBOL})
        connection.execute(text(
            "INSERT INTO stocks(symbol,name) VALUES (:s,'Friday test') ON CONFLICT(symbol) DO NOTHING"
        ), {"s": SYMBOL})
    yield db
    with db.begin() as connection:
        connection.execute(text("DELETE FROM stock_fundamentals_snapshot WHERE symbol=:s"), {"s": SYMBOL})
        connection.execute(text("DELETE FROM adjusted_prices_daily WHERE symbol=:s"), {"s": SYMBOL})
        connection.execute(text("DELETE FROM prices_daily WHERE symbol=:s"), {"s": SYMBOL})
        connection.execute(text("DELETE FROM stocks WHERE symbol=:s"), {"s": SYMBOL})
    db.dispose()


def _raw():
    return {
        "symbol": SYMBOL, "trade_date": DAY,
        "open": Decimal(90), "high": Decimal(110), "low": Decimal(80), "close": Decimal(100),
        "volume": 10, "trade_value": Decimal(1000), "market_cap": Decimal(100000),
        "listed_shares": 1000, "source": "KRX_OPEN_API",
        "market_metadata_source": "KRX_OPEN_API", "zero_volume": False, "raw": {},
    }


def _fundamental():
    return {
        "symbol": SYMBOL, "basis_trade_date": DAY,
        "per": Decimal(10), "pbr": Decimal(2), "eps": Decimal(100), "bps": Decimal(500),
        "w52_high": Decimal(150), "w52_high_date": date(2026, 10, 1),
        "w52_low": Decimal(70), "w52_low_date": date(2025, 11, 3),
        "market_cap": Decimal(100000), "listed_shares": 1000,
        "reference_price": Decimal(100), "final_close": Decimal(100), "source": "KIS",
        "collected_at": datetime(2026, 11, 20, 11, 0, tzinfo=timezone.utc),
        "analysis_per": Decimal(1), "analysis_pbr": Decimal("0.2"),
    }


def _adjusted(close=Decimal(100)):
    return {
        "symbol": SYMBOL, "trade_date": DAY,
        "open": close, "high": close, "low": close, "close": close, "volume": 10,
        "source": "KIS", "adjustment_basis": "KIS_FID_ORG_ADJ_PRC_0_V1",
        "collected_at": datetime(2026, 11, 23, 0, 0, tzinfo=timezone.utc),
    }


def test_strict_insert_is_idempotent_and_never_overwrites(engine):
    first = friday.save_raw_bundle([_raw()], [_fundamental()], engine=engine)
    second = friday.save_raw_bundle([_raw()], [_fundamental()], engine=engine)
    assert first["raw_inserted"] == first["fundamentals_inserted"] == 1
    assert second["raw_existing"] == second["fundamentals_existing"] == 1
    assert friday.save_adjusted_row(_adjusted(), engine=engine) == "inserted"
    assert friday.save_adjusted_row(_adjusted(), engine=engine) == "existing"
    with pytest.raises(friday.FridayConflictError):
        friday.save_adjusted_row(_adjusted(Decimal(50)), engine=engine)
    with engine.connect() as connection:
        row = connection.execute(text("""
            SELECT p.source raw_source, a.source adjusted_source,
                   f.per, f.analysis_per, f.pbr, f.analysis_pbr
            FROM prices_daily p
            JOIN adjusted_prices_daily a USING(symbol,trade_date)
            JOIN stock_fundamentals_snapshot f
              ON f.symbol=p.symbol AND f.basis_trade_date=p.trade_date
            WHERE p.symbol=:s AND p.trade_date=:d
        """), {"s": SYMBOL, "d": DAY}).mappings().one()
    assert row["raw_source"] == "KRX_OPEN_API"
    assert row["adjusted_source"] == "KIS"
    assert row["per"] == Decimal("10.000000")
    assert row["analysis_per"] == Decimal("1.000000")
