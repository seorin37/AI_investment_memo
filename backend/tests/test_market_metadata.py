from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

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


def test_metadata_accepts_uppercase_alphanumeric_symbol():
    result = metadata.normalize_market_metadata(raw_row("00104K"))
    assert result["symbol"] == "00104K"
    assert metadata._target_symbols(("00104K", "0126Z0")) == (
        "00104K", "0126Z0"
    )


@pytest.mark.parametrize("symbol", ["00104k", "00-04K", "12345", "1234567"])
def test_metadata_rejects_invalid_symbol(symbol):
    with pytest.raises(ValueError, match="종목코드"):
        metadata.normalize_market_metadata(raw_row(symbol))


def test_fetch_calls_all_kospi_endpoint_once_and_filters_targets():
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
        symbols=("005930", "000660", "035420", "105560"),
        fetcher=lambda day: calls.append(day) or rows,
    )

    assert calls == [date(2026, 10, 27)]
    assert {row["symbol"] for row in result} == {
        "005930", "000660", "035420", "105560"
    }


def test_fetch_rejects_duplicate_krx_symbol():
    with pytest.raises(ValueError, match="중복 종목"):
        metadata.fetch_market_metadata(
            date(2026, 10, 27),
            symbols=("005930",),
            fetcher=lambda _day: [raw_row("005930"), raw_row("005930")],
        )


def test_903_targets_are_joined_once_and_missing_members_are_reported(monkeypatch):
    monkeypatch.setattr(metadata, "is_krx_trading_day", lambda _day: True)
    targets = tuple(f"{number:06d}" for number in range(1, 904))
    calls = []
    saved_batches = []

    def fetcher(day):
        calls.append(day)
        return [
            raw_row(symbol, day.strftime("%Y%m%d"))
            for symbol in targets[:901]
        ]

    def saver(rows):
        saved_batches.append(rows)
        return {
            "updated_rows": 899,
            "deferred_keys": [
                f"{row['symbol']}:{row['trade_date'].isoformat()}"
                for row in rows[-2:]
            ],
        }

    result = metadata.backfill_market_metadata(
        date(2026, 10, 27),
        date(2026, 10, 27),
        symbols=targets,
        request_interval=0,
        fetcher=fetcher,
        saver=saver,
        check_schema=False,
    )

    assert calls == [date(2026, 10, 27)]
    assert len(saved_batches) == 1
    assert [row["symbol"] for row in saved_batches[0]] == list(targets[:901])
    assert result["target_count"] == 903
    assert result["processed_target_dates"] == 903
    assert result["response_rows"] == 901
    assert result["updated_count"] == 899
    assert result["deferred_count"] == 2
    assert result["missing_keys"] == [
        "000902:2026-10-27", "000903:2026-10-27"
    ]
    assert result["missing_count"] == 2


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
        return [
            raw_row(symbol, day.strftime("%Y%m%d"))
            for symbol in ("005930", "000660", "035420", "105560")
        ]

    result = metadata.backfill_market_metadata(
        date(2026, 10, 27),
        date(2026, 10, 28),
        symbols=("005930", "000660", "035420", "105560"),
        request_interval=0,
        fetcher=fetcher,
        saver=lambda rows: {"updated_rows": len(rows), "deferred_keys": []},
        check_schema=False,
    )

    assert calls == [date(2026, 10, 27), date(2026, 10, 28)]
    assert result["failed_dates"] == ["2026-10-27"]
    assert result["success_dates"] == 1
    assert result["updated_rows"] == 4


def test_deferred_db_keys_are_retried_without_checkpoint(monkeypatch):
    monkeypatch.setattr(metadata, "is_krx_trading_day", lambda _day: True)
    save_calls = []

    def saver(rows):
        save_calls.append(tuple(row["symbol"] for row in rows))
        return {
            "updated_rows": 0,
            "deferred_keys": ["005930:2026-10-27"],
        }

    kwargs = dict(
        start_date=date(2026, 10, 27),
        end_date=date(2026, 10, 27),
        symbols=("005930",),
        request_interval=0,
        fetcher=lambda _day: [raw_row("005930")],
        saver=saver,
        check_schema=False,
    )
    first = metadata.backfill_market_metadata(**kwargs)
    second = metadata.backfill_market_metadata(**kwargs)

    assert save_calls == [("005930",), ("005930",)]
    assert first["deferred_keys"] == second["deferred_keys"] == [
        "005930:2026-10-27"
    ]
