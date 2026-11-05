from __future__ import annotations

from datetime import date
from decimal import Decimal

from pipelines.market import pipeline


def gold_row() -> dict:
    return {
        "product_code": "04020000",
        "trade_date": date(2026, 10, 30),
        "open": Decimal("210000"),
        "high": Decimal("212000"),
        "low": Decimal("209000"),
        "close": Decimal("211000"),
        "volume": 100,
        "trade_value": Decimal("21100000"),
    }


def test_gold_save_registers_master_before_price_without_overwrite(monkeypatch):
    calls = []

    class Result:
        rowcount = 0

    class Connection:
        def execute(self, statement, params):
            calls.append((str(statement), dict(params)))
            return Result()

    class Begin:
        def __enter__(self):
            return Connection()

        def __exit__(self, *_args):
            return False

    class Engine:
        def begin(self):
            return Begin()

        def dispose(self):
            pass

    monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/test")
    monkeypatch.setattr(pipeline, "create_engine", lambda *_args, **_kwargs: Engine())

    assert pipeline.save_gold_price(gold_row()) == 1
    assert len(calls) == 2
    master_sql, master_params = calls[0]
    price_sql, price_params = calls[1]
    assert "INSERT INTO commodity_products" in master_sql
    assert "ON CONFLICT (code) DO NOTHING" in master_sql
    assert "DO UPDATE" not in master_sql
    assert master_params == pipeline.GOLD_PRODUCT
    assert "INSERT INTO commodity_prices_daily" in price_sql
    assert price_params["product_code"] == "04020000"


def test_gold_master_and_price_share_one_transaction(monkeypatch):
    calls = []

    class Connection:
        def execute(self, statement, params):
            calls.append(str(statement))
            if "commodity_products" in str(statement):
                raise RuntimeError("master insert failed")
            raise AssertionError("price insert must not run after master failure")

    class Begin:
        def __enter__(self):
            return Connection()

        def __exit__(self, *_args):
            return False

    class Engine:
        def begin(self):
            return Begin()

        def dispose(self):
            pass

    monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/test")
    monkeypatch.setattr(pipeline, "create_engine", lambda *_args, **_kwargs: Engine())

    try:
        pipeline.save_gold_price(gold_row())
    except RuntimeError as exc:
        assert str(exc) == "master insert failed"
    else:
        raise AssertionError("master failure must propagate")
    assert len(calls) == 1


def test_gold_backfill_uses_the_fk_safe_save_path(monkeypatch):
    saved = []
    monkeypatch.setattr(pipeline, "is_krx_trading_day", lambda _day: True)
    monkeypatch.setattr(pipeline, "load_gold_state", lambda _kind: {})
    monkeypatch.setattr(pipeline, "save_gold_state", lambda *_args: None)
    monkeypatch.setattr(pipeline, "fetch_gold_daily", lambda _day: {"raw": True})
    monkeypatch.setattr(pipeline, "normalize_gold_row", lambda _row: gold_row())
    monkeypatch.setattr(
        pipeline,
        "save_gold_price",
        lambda row: saved.append(row) or 1,
    )

    result = pipeline.backfill_gold_prices(
        date(2026, 10, 30),
        date(2026, 10, 30),
        request_interval=0,
    )

    assert result["success"] == 1
    assert result["failed"] == []
    assert saved == [gold_row()]
