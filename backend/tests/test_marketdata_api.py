"""시세(quote·candles)·뉴스 헤드라인 API 테스트 (중앙 DB 없이)."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_auth_service, get_current_user
from app.marketdata.repository import MarketDataRepository
from app.marketdata.routes import get_marketdata_service, router
from app.marketdata.service import MarketDataService


def _price_rows(n: int, start_close: int = 100_000) -> list[dict]:
    rows = []
    for i in range(n):
        close = Decimal(start_close + i * 100)
        rows.append(
            {
                "trade_date": date(2026, 1, 1) + timedelta(days=i),
                "open": close - 50,
                "high": close + 200,
                "low": close - 300,
                "close": close,
                "volume": 1_000 + i,
            }
        )
    return rows


class FakeRepo:
    def __init__(self) -> None:
        self.prices: dict[str, list[dict]] = {"005930": _price_rows(300)}
        self.news: list[dict] = [
            {
                "id": 11,
                "title": "반도체 강세",
                "summary": "요약",
                "url": "https://example.com/11",
                "published_at": datetime(2026, 11, 20, 4, 0, tzinfo=timezone.utc),
                "source": "연합뉴스",
            },
            {
                "id": 10,
                "title": "환율 하락",
                "summary": None,
                "url": "https://example.com/10",
                "published_at": datetime(2026, 11, 20, 3, 0, tzinfo=timezone.utc),
                "source": "매일경제",
            },
        ]
        self.news_limits: list[int] = []

    def recent_prices(self, code, limit):
        return self.prices.get(code, [])[-limit:]

    def latest_news(self, limit):
        self.news_limits.append(limit)
        return self.news[:limit]


class MarketDataApiTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"id": "7"}
        app.dependency_overrides[get_marketdata_service] = lambda: MarketDataService(self.repo)
        self.client = TestClient(app)

    # ─── quote
    def test_quote_matches_mock_shape(self):
        res = self.client.get("/api/v1/stocks/005930/quote")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(set(body), {"code", "price", "change", "change_pct", "as_of", "spark"})
        last = 100_000 + 299 * 100
        self.assertEqual(body["code"], "005930")
        self.assertEqual(body["price"], last)
        self.assertIsInstance(body["price"], int)
        self.assertEqual(body["change"], 100)
        self.assertEqual(body["change_pct"], round(100 / (last - 100) * 100, 2))
        self.assertEqual(body["as_of"], "2026-10-27T15:30:00+09:00")
        self.assertEqual(len(body["spark"]), 24)
        self.assertEqual(body["spark"][-1], last)

    def test_quote_with_single_day_has_zero_change(self):
        self.repo.prices["000660"] = _price_rows(1)
        body = self.client.get("/api/v1/stocks/000660/quote").json()
        self.assertEqual((body["change"], body["change_pct"]), (0, 0.0))

    def test_quote_unknown_code_is_404(self):
        self.assertEqual(self.client.get("/api/v1/stocks/999999/quote").status_code, 404)

    def test_invalid_code_is_422(self):
        self.assertEqual(self.client.get("/api/v1/stocks/abc/quote").status_code, 422)

    # ─── candles
    def test_candles_use_mock_range_sizes(self):
        for range_, size in {"1W": 5, "1M": 22, "3M": 64, "1Y": 250}.items():
            with self.subTest(range=range_):
                res = self.client.get("/api/v1/stocks/005930/candles", params={"range": range_})
                self.assertEqual(res.status_code, 200)
                self.assertEqual(len(res.json()), size)

    def test_candle_shape_and_order(self):
        body = self.client.get("/api/v1/stocks/005930/candles", params={"range": "1W"}).json()
        self.assertEqual(set(body[0]), {"date", "open", "high", "low", "close", "volume"})
        self.assertEqual([c["date"] for c in body], sorted(c["date"] for c in body))
        self.assertEqual(body[-1]["date"], "2026-10-27")
        self.assertEqual(body[-1]["close"], 129_900)

    def test_candles_reject_unknown_range(self):
        res = self.client.get("/api/v1/stocks/005930/candles", params={"range": "5Y"})
        self.assertEqual(res.status_code, 422)

    def test_candles_unknown_code_is_404(self):
        res = self.client.get("/api/v1/stocks/999999/candles", params={"range": "1M"})
        self.assertEqual(res.status_code, 404)

    # ─── news
    def test_headlines_shape(self):
        res = self.client.get("/api/v1/news/headlines")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json()[0],
            {
                "id": "11",
                "title": "반도체 강세",
                "summary": "요약",
                "source": "연합뉴스",
                "url": "https://example.com/11",
                "published_at": "2026-11-20T04:00:00+00:00",
            },
        )
        self.assertEqual(self.repo.news_limits, [20])

    def test_headlines_limit_bounds(self):
        self.assertEqual(len(self.client.get("/api/v1/news/headlines", params={"limit": 1}).json()), 1)
        self.assertEqual(self.client.get("/api/v1/news/headlines", params={"limit": 51}).status_code, 422)

    def test_requires_authentication(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_service] = lambda: None
        app.dependency_overrides[get_marketdata_service] = lambda: None
        client = TestClient(app)
        for path in ("/api/v1/stocks/005930/quote", "/api/v1/stocks/005930/candles", "/api/v1/news/headlines"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 401)


class RecordingSession:
    def __init__(self, rows):
        self.rows = rows
        self.sql = []

    def execute(self, statement, params=None):
        self.sql.append(str(statement))
        rows = self.rows

        class Result:
            def mappings(self):
                return self

            def all(self):
                return rows

        return Result()


class MarketDataRepositorySqlTest(unittest.TestCase):
    def test_recent_prices_returns_ascending(self):
        rows = [{"trade_date": date(2026, 1, 3)}, {"trade_date": date(2026, 1, 2)}]
        result = MarketDataRepository(RecordingSession(rows)).recent_prices("005930", 2)
        self.assertEqual([r["trade_date"].day for r in result], [2, 3])

    def test_news_query_does_not_touch_bodies_or_chunks(self):
        session = RecordingSession([])
        MarketDataRepository(session).latest_news(5)
        self.assertNotIn("news_article_bodies", session.sql[0])
        self.assertNotIn("news_chunks", session.sql[0])
        self.assertIn("ORDER BY a.published_at DESC", session.sql[0])


if __name__ == "__main__":
    unittest.main()
