from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from scripts.copy_preferred_descriptions import Stock, build_plan, run


DESCRIPTION = "본주는 여러 제품과 서비스를 제공하는 회사예요. 주요 사업을 안정적으로 운영하며 고객에게 제품을 공급하고 있어요."


def stock(symbol, name, description=None, corp=None):
    return Stock(symbol, name, corp, "KOSPI", description)


def test_build_plan_copies_only_blank_preferred_stocks():
    stocks = [
        stock("000100", "본주", DESCRIPTION),
        stock("000105", "본주우"),
        stock("000107", "본주2우B", DESCRIPTION),
    ]
    updates, summary = build_plan(stocks)

    assert updates == [("000105", "000100")]
    assert summary["preferred_total"] == 2
    assert summary["already_matching"] == 1
    assert summary["update_candidates"] == 1
    assert summary["nonblank_different"] == []


def test_build_plan_never_overwrites_nonblank_different_text():
    stocks = [
        stock("000100", "본주", DESCRIPTION),
        stock("000105", "본주우", "기존 우선주 설명"),
    ]
    updates, summary = build_plan(stocks)

    assert updates == []
    assert summary["update_candidates"] == 0
    assert summary["nonblank_different"][0]["symbol"] == "000105"


def test_build_plan_reports_missing_common_description():
    stocks = [stock("000100", "본주"), stock("000105", "본주우")]
    updates, summary = build_plan(stocks)

    assert updates == []
    assert summary["source_missing"][0]["common"] == "000100"


def test_build_plan_reports_unmapped_preferred_stock():
    updates, summary = build_plan([stock("999995", "고립우")])

    assert updates == []
    assert summary["unmapped"] == [{"symbol": "999995", "name": "고립우"}]


def test_apply_on_local_test_database():
    root = Path(__file__).resolve().parents[2]
    raw_url = dotenv_values(root / ".env.test").get("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("TEST_DATABASE_URL이 없습니다")
    url = make_url(raw_url)
    assert url.host in {"127.0.0.1", "localhost"}
    assert url.port == 5433
    assert "test" in (url.database or "").lower()
    engine = create_engine(url.set(drivername="postgresql+psycopg"))
    try:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM stocks WHERE symbol IN ('999990', '999995')")
            )
            connection.execute(
                text(
                    """
                    INSERT INTO stocks(symbol, name, description) VALUES
                    ('999990', '검증본주', :description),
                    ('999995', '검증본주우', NULL)
                    """
                ),
                {"description": DESCRIPTION},
            )

        result = run(engine=engine, apply=True)
        assert result["update_candidates"] == 1
        assert result["updated_rows"] == 1
        assert result["post_verified_rows"] == 1
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT btrim(symbol), description
                    FROM stocks
                    WHERE symbol IN ('999990', '999995')
                    ORDER BY symbol
                    """
                )
            ).fetchall()
        assert len(rows) == 2
        assert rows[0][1] == rows[1][1] == DESCRIPTION
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM stocks WHERE symbol IN ('999990', '999995')")
            )
        engine.dispose()
