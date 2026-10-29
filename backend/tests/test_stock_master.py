from datetime import date

import pytest

from pipelines.market import stock_master
from pipelines.market import krx


def raw(symbol="005930", name="삼성전자", market="KOSPI"):
    if market == "KOSPI":
        return {
            "ISU_CD": f"KR7{symbol}003",
            "ISU_SRT_CD": symbol,
            "ISU_NM": f"{name} 보통주",
            "ISU_ABBRV": name,
            "MKT_TP_NM": "KOSPI",
        }
    return {"ISU_CD": symbol, "ISU_NM": name, "MKT_NM": market}


def test_normalize_kospi_snapshot_filters_other_markets_and_validates_symbols():
    rows = stock_master.normalize_kospi_snapshot(
        [raw(), raw("000660", "SK하이닉스"), raw("247540", "에코프로비엠", "KOSDAQ")]
    )
    assert rows == [
        {"symbol": "005930", "name": "삼성전자", "market": "KOSPI", "sector": "general"},
        {"symbol": "000660", "name": "SK하이닉스", "market": "KOSPI", "sector": "general"},
    ]
    with pytest.raises(ValueError, match="종목코드"):
        stock_master.normalize_kospi_snapshot([raw("A05930")])
    with pytest.raises(ValueError, match="중복"):
        stock_master.normalize_kospi_snapshot([raw(), raw(name="삼성전자 변경")])
    with pytest.raises(ValueError, match="비어"):
        stock_master.normalize_kospi_snapshot([])


def test_fetch_kospi_stock_master_uses_official_base_info_endpoint(monkeypatch):
    seen = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"OutBlock_1": [raw()]}

    def fake_get(url, **kwargs):
        seen.update(url=url, **kwargs)
        return Response()

    monkeypatch.setenv("KRX_API_KEY", "test-key")
    monkeypatch.setattr(krx.requests, "get", fake_get)
    assert krx.fetch_kospi_stock_master(date(2026, 10, 28)) == [raw()]
    assert seen["url"] == krx.KRX_KOSPI_STOCK_MASTER_URL
    assert seen["params"] == {"basDd": "20261028"}
    assert seen["timeout"] == 30
    assert seen["headers"] == {"AUTH_KEY": "test-key"}


def test_sync_fetches_once_and_passes_full_normalized_snapshot():
    calls = []
    saved = []

    def fetcher(day):
        calls.append(day)
        return [raw(), raw("000660", "SK하이닉스")]

    def saver(rows):
        saved.extend(rows)
        return {"received": 2, "inserted": 2, "updated": 0, "unchanged": 0}

    result = stock_master.sync_kospi_stocks(
        date(2026, 10, 28), fetcher=fetcher, saver=saver
    )
    assert calls == [date(2026, 10, 28)]
    assert [row["symbol"] for row in saved] == ["005930", "000660"]
    assert result == {
        "trade_date": "2026-10-28",
        "minimum_required": 1,
        "failed_count": 0,
        "received": 2,
        "inserted": 2,
        "updated": 0,
        "unchanged": 0,
    }


def test_sync_rejects_obviously_incomplete_snapshot_before_saving():
    saved = False

    def saver(_rows):
        nonlocal saved
        saved = True
        return {}

    with pytest.raises(ValueError, match="명백히 불완전"):
        stock_master.sync_kospi_stocks(
            date(2026, 10, 28),
            fetcher=lambda _day: [raw(), raw("000660", "SK하이닉스")],
            saver=saver,
            minimum_count=3,
        )
    assert saved is False

    with pytest.raises(ValueError, match="최소 8건"):
        stock_master.sync_kospi_stocks(
            date(2026, 10, 28),
            fetcher=lambda _day: [
                raw(f"{number:06d}", f"종목{number}")
                for number in range(1, 8)
            ],
            saver=saver,
            existing_count=10,
            minimum_existing_ratio=0.8,
        )
    assert saved is False


def test_load_kospi_symbols_fails_when_database_universe_is_empty():
    class Result:
        def scalars(self):
            return iter(())

    class Connection:
        def execute(self, _statement):
            return Result()

    class Connect:
        def __enter__(self):
            return Connection()

        def __exit__(self, *_args):
            return False

    class Engine:
        def connect(self):
            return Connect()

    with pytest.raises(ValueError, match="종목 마스터를 먼저 등록"):
        stock_master.load_kospi_symbols(engine=Engine())
