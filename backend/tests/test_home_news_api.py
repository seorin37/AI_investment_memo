"""홈 뉴스 위젯 API (GET /api/v1/news/home) 테스트 (중앙 DB 없이)."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_current_user
from app.marketdata.routes import get_marketdata_service, router as marketdata_router
from app.marketdata.service import MarketDataService

KST = ZoneInfo("Asia/Seoul")


class FakeNewsRepo:
    def __init__(self, rows: list[dict], counts: dict[str, int] | None = None) -> None:
        self.rows = rows
        self.counts = counts or {}
        self.count_calls: list[tuple[datetime, datetime]] = []
        self.limits: list[int] = []

    def latest_news(self, limit):
        self.limits.append(limit)
        return self.rows[:limit]

    def linked_news_count(self, start, end):
        self.count_calls.append((start, end))
        return self.counts.get(start.date().isoformat(), 0)


def _row(i: int, published_at: datetime, codes=("005930",)) -> dict:
    return {
        "id": i,
        "title": f"기사 {i}",
        "summary": "요약",
        "url": f"https://news.example/{i}",
        "published_at": published_at,
        "source": "한국경제",
        "stock_codes": list(codes),
    }


def _client(repo: FakeNewsRepo) -> TestClient:
    app = FastAPI()
    app.include_router(marketdata_router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "7"}
    app.dependency_overrides[get_marketdata_service] = lambda: MarketDataService(repo)
    return TestClient(app)


class HomeNewsTest(unittest.TestCase):
    def test_shape_matches_home_news_item_in_kst(self):
        # UTC 15:30 = KST 다음날 00:30 → 날짜는 KST 기준이어야 한다
        utc = datetime(2026, 11, 20, 15, 30, tzinfo=timezone.utc)
        repo = FakeNewsRepo(
            [_row(2, utc), _row(1, utc - timedelta(hours=1), codes=())],
            counts={"2026-11-21": 44},
        )
        body = _client(repo).get("/api/v1/news/home").json()

        self.assertEqual(body["day"], "2026-11-21")
        self.assertEqual(body["day_total"], 44)
        self.assertEqual(
            body["items"][0],
            {
                "id": "2",
                "title": "기사 2",
                "src": "한국경제",
                "at": "2026-11-21T00:30:00+09:00",
                "url": "https://news.example/2",
                "stock_codes": ["005930"],
            },
        )
        self.assertEqual(body["items"][1]["at"][:10], "2026-11-20")
        self.assertEqual(body["items"][1]["stock_codes"], [])

    def test_day_total_counts_the_whole_kst_day(self):
        repo = FakeNewsRepo([_row(1, datetime(2026, 11, 21, 14, 0, tzinfo=KST))])
        _client(repo).get("/api/v1/news/home")
        start, end = repo.count_calls[0]
        self.assertEqual(start, datetime(2026, 11, 21, 0, 0, tzinfo=KST))
        self.assertEqual(end - start, timedelta(days=1))

    def test_same_title_from_several_outlets_shows_once(self):
        t = datetime(2026, 11, 20, 9, 20, tzinfo=KST)
        rows = [_row(1, t), _row(2, t - timedelta(minutes=5)), _row(3, t - timedelta(minutes=9))]
        rows[0]["title"] = "[속보] 코스피  사이드카 발동"
        rows[1]["title"] = " [속보] 코스피 사이드카 발동"  # 빈칸만 다름 → 같은 제목
        rows[1]["source"] = "서울경제"
        rows += [_row(i, t - timedelta(minutes=10 + i)) for i in range(4, 12)]
        body = _client(FakeNewsRepo(rows)).get("/api/v1/news/home").json()
        ids = [it["id"] for it in body["items"]]
        self.assertEqual(ids[0], "1")  # 가장 새 기사가 남는다
        self.assertNotIn("2", ids)
        self.assertEqual(len(ids), 9)  # 걸러진 만큼 뒤에서 채운다

    def test_default_limit_is_nine_and_bounded(self):
        repo = FakeNewsRepo([])
        client = _client(repo)
        client.get("/api/v1/news/home")
        self.assertEqual(repo.limits, [27])  # 같은 제목을 거르려고 3배 받는다
        self.assertEqual(client.get("/api/v1/news/home?limit=0").status_code, 422)
        self.assertEqual(client.get("/api/v1/news/home?limit=51").status_code, 422)

    def test_empty_news(self):
        repo = FakeNewsRepo([])
        body = _client(repo).get("/api/v1/news/home").json()
        self.assertEqual(body, {"day": None, "day_total": 0, "items": []})
        self.assertEqual(repo.count_calls, [])


if __name__ == "__main__":
    unittest.main()
