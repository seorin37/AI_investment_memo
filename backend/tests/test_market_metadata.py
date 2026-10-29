from __future__ import annotations

from datetime import date
from decimal import Decimal

from pipelines.market import metadata


def raw_row(symbol="005930", day="20261027", market_cap="1000000", shares="1000"):
    return {
        "MKT_NM": "KOSPI",
        "ISU_CD": symbol,
        "BAS_DD": day,
        "MKTCAP": market_cap,
        "LIST_SHRS": shares,
        # These values must never be normalized or persisted by this module.
        "TDD_OPNPRC": "999",
        "TDD_CLSPRC": "888",
    }


def test_normalize_uses_only_daily_market_metadata():
    result = metadata.normalize_market_metadata(raw_row())

    assert result == {
        "symbol": "005930",
        "trade_date": date(2026, 10, 27),
        "market_cap": Decimal("1000000"),
        "listed_shares": 1000,
        "market_metadata_source": "KRX_OPEN_API",
    }
    assert not {"open", "high", "low", "close", "volume"} & result.keys()


def test_fetch_calls_all_kospi_endpoint_once_and_filters_pilots():
    calls = []
    rows = [
        raw_row("005930"),
        raw_row("000660"),
        raw_row("035420"),
        raw_row("105560"),
        {**raw_row("999999"), "ISU_CD": "999999"},
    ]

    result = metadata.fetch_market_metadata(
        date(2026, 10, 27),
        fetcher=lambda day: calls.append(day) or rows,
    )

    assert calls == [date(2026, 10, 27)]
    assert {row["symbol"] for row in result} == set(metadata.PILOT_SYMBOLS)


def test_save_updates_only_existing_kis_rows_and_defers_missing(monkeypatch):
    statements = []

    class ScalarRows:
        def scalars(self):
            return iter(["005930"])

    class Connection:
        def execute(self, statement, params=None):
            statements.append((str(statement), params))
            if str(statement).lstrip().startswith("SELECT"):
                return ScalarRows()
            return object()

    class Begin:
        def __enter__(self):
            return Connection()

        def __exit__(self, *_):
            return False

    class Engine:
        def begin(self):
            return Begin()

    monkeypatch.setattr(metadata, "get_engine", lambda: Engine())
    rows = [
        metadata.normalize_market_metadata(raw_row("005930")),
        metadata.normalize_market_metadata(raw_row("000660")),
    ]

    result = metadata.save_market_metadata(rows)

    assert result == {
        "updated_rows": 1,
        "deferred_keys": ["000660:2026-10-27"],
    }
    update_sql, update_rows = statements[1]
    assert "UPDATE prices_daily" in update_sql
    assert "source = 'KIS'" in update_sql
    assert "open" not in update_sql.lower()
    assert [row["symbol"] for row in update_rows] == ["005930"]


def test_backfill_isolates_failed_date_and_continues(monkeypatch):
    monkeypatch.setattr(metadata, "is_krx_trading_day", lambda _day: True)
    calls = []

    def fetcher(day):
        calls.append(day)
        if day == date(2026, 10, 27):
            raise RuntimeError("temporary")
        return [raw_row(symbol, day.strftime("%Y%m%d")) for symbol in metadata.PILOT_SYMBOLS]

    result = metadata.backfill_market_metadata(
        date(2026, 10, 27),
        date(2026, 10, 28),
        request_interval=0,
        fetcher=fetcher,
        saver=lambda rows: {"updated_rows": len(rows), "deferred_keys": []},
        check_schema=False,
    )

    assert calls == [date(2026, 10, 27), date(2026, 10, 28)]
    assert result["failed_dates"] == ["2026-10-27"]
    assert result["success_dates"] == 1
    assert result["updated_rows"] == 4
