from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from scripts import replay_market_recovery_20261120_23 as recovery


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return iter(self._rows)


class _Connection:
    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table

    def execute(self, statement, _params):
        sql = str(statement)
        table = next(table for table in self.rows_by_table if f"FROM {table}" in sql)
        return _Rows(self.rows_by_table[table])


def _groups(trade_date: date):
    price = {
        "symbol": "005930",
        "trade_date": trade_date,
        "open": Decimal("100"),
        "high": Decimal("110"),
        "low": Decimal("90"),
        "close": Decimal("105"),
        "volume": 10,
        "trade_value": Decimal("1000"),
        "market_cap": None if trade_date == recovery.ALLOWED_DATES[1] else Decimal("5000"),
        "listed_shares": None if trade_date == recovery.ALLOWED_DATES[1] else 50,
        "source": "KIS" if trade_date == recovery.ALLOWED_DATES[1] else "KRX_OPEN_API",
        "market_metadata_source": None if trade_date == recovery.ALLOWED_DATES[1] else "KRX_OPEN_API",
    }
    adjusted = {
        "symbol": "005930",
        "trade_date": trade_date,
        "open": Decimal("100"),
        "high": Decimal("110"),
        "low": Decimal("90"),
        "close": Decimal("105"),
        "volume": 10,
        "source": "KIS",
        "adjustment_basis": "KIS_FID_ORG_ADJ_PRC_0_V1",
        "collected_at": datetime(2026, 11, 24, tzinfo=timezone.utc),
    }
    fundamental = {
        "symbol": "005930",
        "basis_trade_date": trade_date,
        "per": Decimal("10"),
        "pbr": Decimal("1"),
        "eps": Decimal("10"),
        "bps": Decimal("100"),
        "w52_high": Decimal("120"),
        "w52_high_date": date(2026, 10, 1),
        "w52_low": Decimal("80"),
        "w52_low_date": date(2026, 9, 1),
        "market_cap": Decimal("5000"),
        "listed_shares": 50,
        "reference_price": Decimal("105"),
        "final_close": Decimal("105"),
        "source": "KIS",
        "collected_at": datetime(2026, 11, 24, tzinfo=timezone.utc),
    }
    return ([price], [adjusted], [fundamental])


@pytest.mark.parametrize("trade_date", recovery.ALLOWED_DATES)
def test_inspect_state_uses_each_tables_date_column(trade_date):
    groups = _groups(trade_date)
    current_price = dict(groups[0][0])
    if trade_date == recovery.ALLOWED_DATES[1]:
        current_price.update(
            market_cap=Decimal("5000"),
            listed_shares=50,
            market_metadata_source="KRX_OPEN_API",
        )
    connection = _Connection({
        "prices_daily": [current_price],
        "adjusted_prices_daily": [dict(groups[1][0])],
        "stock_fundamentals_snapshot": [dict(groups[2][0])],
    })
    columns = (
        list(recovery.PRICE_COLUMNS),
        list(recovery.ADJUSTED_COLUMNS),
        list(recovery.FUNDAMENTAL_COLUMNS_0023),
    )

    state, conflicts = recovery.inspect_state(connection, trade_date, groups, columns)

    assert conflicts == []
    assert all(item == {"expected": 1, "existing_identical": 1, "missing": 0}
               for item in state.values())


def test_inspect_state_still_reports_core_value_conflict():
    trade_date = recovery.ALLOWED_DATES[1]
    groups = _groups(trade_date)
    bad_fundamental = dict(groups[2][0], final_close=Decimal("106"))
    connection = _Connection({
        "prices_daily": [dict(groups[0][0])],
        "adjusted_prices_daily": [dict(groups[1][0])],
        "stock_fundamentals_snapshot": [bad_fundamental],
    })
    columns = (
        list(recovery.PRICE_COLUMNS),
        list(recovery.ADJUSTED_COLUMNS),
        list(recovery.FUNDAMENTAL_COLUMNS_0023),
    )

    _state, conflicts = recovery.inspect_state(connection, trade_date, groups, columns)

    assert conflicts == [{
        "table": "stock_fundamentals_snapshot",
        "symbol": "005930",
        "columns": ["final_close"],
    }]


def test_conflict_check_rejects_missing_table_date_column():
    with pytest.raises(recovery.RecoveryError, match="basis_trade_date"):
        recovery._conflicts(
            {},
            {"symbol": "005930"},
            recovery.FUNDAMENTAL_COLUMNS_0023,
            date_column="basis_trade_date",
        )
