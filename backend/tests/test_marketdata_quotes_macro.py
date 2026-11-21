"""여러 종목 시세(GET /quotes)·거시 지표(GET /market/macro)·지수 날짜(C-16) 테스트 (DB 없이)."""

from __future__ import annotations

import unittest
from datetime import date, timedelta
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_current_user
from app.marketdata.repository import MarketDataRepository
from app.marketdata.routes import get_marketdata_service, router
from app.marketdata.service import MarketDataService


def _closes(n: int, start: int) -> list[dict]:
    return [{"trade_date": date(2026, 11, 1) + timedelta(days=i), "close": Decimal(start + i * 100)} for i in range(n)]


def _days(n: int, start: float) -> list[dict]:
    return [{"day": date(2025, 1, 1) + timedelta(days=i), "value": Decimal(str(start + i))} for i in range(n)]


class FakeRepo:
    def __init__(self) -> None:
        self.prices = {"005930": _closes(30, 70_000), "000660": _closes(3, 180_000)}
        self.many_calls: list[tuple[list[str], int]] = []
        self.obs = {
            "USD_KRW": [
                {"day": date(2026, 11, 19), "value": Decimal("1395.10000000"), "source": "ECOS", "series_code": None},
                {"day": date(2026, 11, 20), "value": Decimal("1401.30000000"), "source": "ECOS", "series_code": None},
            ],
            "US_TREASURY_10Y": [
                {"day": date(2026, 11, 20), "value": Decimal("4.32000000"), "source": "FRED", "series_code": "DGS10"},
            ],
        }
        self.obs_calls: list[list[str]] = []
        self.gold = [
            {"day": date(2026, 11, 19), "value": Decimal("190000.0000"), "source": "KRX", "series_code": "04020000"},
            {"day": date(2026, 11, 20), "value": Decimal("191900.0000"), "source": "KRX", "series_code": "04020000"},
        ]

    # quotes
    def recent_prices(self, code, limit):
        return self.prices.get(code, [])[-limit:]

    def recent_prices_many(self, codes, limit):
        self.many_calls.append((list(codes), limit))
        return {c: self.prices[c][-limit:] for c in codes if c in self.prices}

    # overview
    def index_closes(self, code, limit):
        return _days(300, 2500.0)[-limit:] if code == "KOSPI" else []

    def observations(self, code, limit):
        return []

    def commodity_closes(self, code, limit):
        return []

    # macro
    def latest_observations(self, codes, per_code):
        self.obs_calls.append(list(codes))
        return {c: self.obs[c][-per_code:] for c in codes if c in self.obs}

    def latest_commodity(self, code, n):
        return self.gold[-n:] if code == "04020000" else []


class QuotesMacroApiTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"id": "7"}
        app.dependency_overrides[get_marketdata_service] = lambda: MarketDataService(self.repo)
        self.client = TestClient(app)

    def test_quotes_many_in_one_call_keeps_order_and_reports_missing(self):
        res = self.client.get("/api/v1/quotes", params={"codes": "000660, 005930,123456,005930"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual([q["code"] for q in body["quotes"]], ["000660", "005930"])
        self.assertEqual(body["missing"], ["123456"])
        # 중복은 한 번만, DB 는 한 번만 읽는다
        self.assertEqual(self.repo.many_calls, [(["000660", "005930", "123456"], 24)])

    def test_quote_has_trade_date_and_raw_close_change(self):
        q = self.client.get("/api/v1/quotes", params={"codes": "000660"}).json()["quotes"][0]
        self.assertEqual(q["trade_date"], "2026-11-03")
        self.assertEqual(q["as_of"], "2026-11-03T15:30:00+09:00")
        self.assertEqual((q["price"], q["change"]), (180_200, 100))
        self.assertEqual(q["spark"], [180_000, 180_100, 180_200])
        single = self.client.get("/api/v1/stocks/000660/quote").json()
        self.assertEqual(single, q)  # 한 종목 API 와 같은 모양

    def test_quotes_rejects_bad_codes(self):
        for codes in ("", "12345", "005930,abc!!!", ",".join(f"{i:06d}" for i in range(51))):
            self.assertEqual(self.client.get("/api/v1/quotes", params={"codes": codes}).status_code, 422, codes)

    def test_overview_index_has_dates_aligned_with_series(self):
        idx = self.client.get("/api/v1/market/overview").json()["indices"][0]
        self.assertEqual(idx["key"], "KOSPI")
        self.assertEqual(len(idx["dates"]), len(idx["series"]["1Y"]))
        self.assertEqual(idx["trade_date"], idx["dates"][-1])
        self.assertEqual(idx["dates"][-1], (date(2025, 1, 1) + timedelta(days=299)).isoformat())

    def test_macro_latest_prev_date_source(self):
        body = self.client.get("/api/v1/market/macro").json()
        by = {i["key"]: i for i in body["indicators"]}
        usd = by["USD_KRW"]
        self.assertEqual((usd["value"], usd["prev_value"], usd["change"]), (1401.3, 1395.1, 6.2))
        self.assertEqual((usd["observed_date"], usd["prev_date"], usd["source"]), ("2026-11-20", "2026-11-19", "ECOS"))
        us10 = by["US_TREASURY_10Y"]
        self.assertEqual((us10["value"], us10["prev_value"], us10["change"], us10["change_pct"]), (4.32, None, None, None))
        self.assertEqual((us10["source"], us10["series_code"]), ("FRED", "DGS10"))
        gold = by["GOLD"]
        self.assertEqual((gold["value"], gold["change_pct"], gold["source"], gold["unit"]), (191900.0, 1.0, "KRX", "원/g"))
        self.assertIn("KR_POLICY_RATE", body["missing"])
        self.assertEqual(body["as_of"], "2026-11-20")
        # 관측값은 한 번에 읽는다 (금은 commodity 표)
        self.assertEqual(len(self.repo.obs_calls), 1)
        self.assertNotIn("04020000", self.repo.obs_calls[0])


class RecordingSession:
    def __init__(self, rows):
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement, params=None):
        self.calls.append((" ".join(str(statement).split()), params or {}))
        rows = self.rows

        class Result:
            def mappings(self):
                return self

            def all(self):
                return rows

        return Result()


class QuotesMacroSqlTest(unittest.TestCase):
    def test_many_prices_read_only_raw_table_grouped(self):
        rows = [{"code": "000660", "trade_date": date(2026, 1, 2), "close": 1}, {"code": "005930", "trade_date": date(2026, 1, 2), "close": 2}]
        session = RecordingSession(rows)
        out = MarketDataRepository(session).recent_prices_many(["000660", "005930"], 24)
        sql, params = session.calls[0]
        self.assertTrue(sql.startswith("SELECT"))
        self.assertIn("FROM prices_daily", sql)
        self.assertNotIn("adjusted_prices_daily", sql)  # 현재가·등락은 원시 종가
        self.assertEqual(params, {"codes": ["000660", "005930"], "limit": 24})
        self.assertEqual(sorted(out), ["000660", "005930"])

    def test_macro_sql_reads_observations_and_indicator_source(self):
        session = RecordingSession([])
        MarketDataRepository(session).latest_observations(["USD_KRW"], 2)
        sql, params = session.calls[0]
        self.assertIn("FROM economic_observations", sql)
        self.assertIn("JOIN economic_indicators", sql)
        self.assertEqual(params["n"], 2)
        for word in ("INSERT", "UPDATE", "DELETE"):
            self.assertNotIn(word, sql.upper())


if __name__ == "__main__":
    unittest.main()
