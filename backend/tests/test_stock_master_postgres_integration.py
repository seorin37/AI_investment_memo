"""PostgreSQL integration test for an explicitly isolated local database."""

from __future__ import annotations

import os
from datetime import date

import pytest
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import make_url

from pipelines.market.stock_master import load_kospi_symbols, save_kospi_stocks


TEST_URL_ENV = "STOCK_MASTER_INTEGRATION_DATABASE_URL"
SYMBOLS = ("999901", "999902", "999903")


def _isolated_url() -> str:
    raw = os.environ.get(TEST_URL_ENV)
    if not raw:
        pytest.skip(f"{TEST_URL_ENV} is not set")
    url = make_url(raw)
    database = (url.database or "").lower()
    if (
        url.host not in {"127.0.0.1", "localhost"}
        or url.port in {None, 5432}
        or "test" not in database
    ):
        pytest.fail("stock-master integration database is not an isolated local test database")
    return raw


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(_isolated_url(), pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM prices_daily WHERE symbol IN :symbols").bindparams(
            bindparam("symbols", expanding=True)
        ), {"symbols": SYMBOLS})
        connection.execute(text("DELETE FROM stocks WHERE symbol IN :symbols").bindparams(
            bindparam("symbols", expanding=True)
        ), {"symbols": SYMBOLS})
        connection.execute(
            text(
                """
                INSERT INTO stocks (symbol, name, market, sector, dart_corp_code, description)
                VALUES
                  ('999901', '이전 이름', 'KOSDAQ', 'financial', '12345678', '보존 설명'),
                  ('999903', '스냅샷 부재 종목', 'KOSPI', 'general', NULL, NULL)
                """
            )
        )
    yield engine
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM prices_daily WHERE symbol IN :symbols").bindparams(
            bindparam("symbols", expanding=True)
        ), {"symbols": SYMBOLS})
        connection.execute(text("DELETE FROM stocks WHERE symbol IN :symbols").bindparams(
            bindparam("symbols", expanding=True)
        ), {"symbols": SYMBOLS})
    engine.dispose()


def test_upsert_is_idempotent_preserves_metadata_absent_rows_and_fk(pg_engine):
    snapshot = [
        {"symbol": "999901", "name": "변경 이름", "market": "KOSPI", "sector": "general"},
        {"symbol": "999902", "name": "신규 종목", "market": "KOSPI", "sector": "general"},
    ]
    first = save_kospi_stocks(snapshot, engine=pg_engine)
    assert {key: first[key] for key in ("received", "inserted", "updated", "unchanged")} == {
        "received": 2, "inserted": 1, "updated": 1, "unchanged": 0
    }
    assert first["preserved_absent"] == len(first["preserved_absent_symbols"])
    assert "999903" in first["preserved_absent_symbols"]

    second = save_kospi_stocks(snapshot, engine=pg_engine)
    assert {key: second[key] for key in ("received", "inserted", "updated", "unchanged")} == {
        "received": 2, "inserted": 0, "updated": 0, "unchanged": 2
    }
    assert second["preserved_absent_symbols"] == first["preserved_absent_symbols"]
    with pg_engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT symbol, name, market::text, sector::text, dart_corp_code, description
                FROM stocks WHERE symbol IN ('999901', '999902', '999903')
                ORDER BY symbol
                """
            )
        ).all()
        assert rows == [
            ("999901", "변경 이름", "KOSPI", "financial", "12345678", "보존 설명"),
            ("999902", "신규 종목", "KOSPI", "general", None, None),
            ("999903", "스냅샷 부재 종목", "KOSPI", "general", None, None),
        ]
        connection.execute(
            text(
                """
                INSERT INTO prices_daily (
                  symbol, trade_date, open, high, low, close, volume, source
                ) VALUES (
                  '999902', :trade_date, 100, 110, 90, 105, 1000, 'KIS'
                )
                """
            ),
            {"trade_date": date(2026, 10, 28)},
        )
        assert connection.execute(
            text("SELECT count(*) FROM prices_daily WHERE symbol='999902'")
        ).scalar_one() == 1


def test_target_selection_supports_explicit_codes_and_limit(pg_engine):
    all_symbols = load_kospi_symbols(engine=pg_engine)
    assert tuple(sorted(all_symbols)) == all_symbols
    assert {"999901", "999903"} <= set(all_symbols)
    assert load_kospi_symbols(
        symbols=("999903", "999901"), limit=1, engine=pg_engine
    ) == ("999903",)
    with pytest.raises(ValueError, match="stocks에 없는"):
        load_kospi_symbols(symbols=("999999",), engine=pg_engine)
