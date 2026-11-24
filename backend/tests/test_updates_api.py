"""카드 조회 API (2026-11-11). DB 없이: 서비스 변환(가짜 저장소)과 경로(가짜 서비스)."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_current_user
from app.updates.routes import get_command_service, get_query_service, router
from app.updates.service import MemoNotFoundError, UpdateNotFoundError, UpdatesService

T = datetime(2026, 11, 11, 6, 30, tzinfo=timezone.utc)


def card(uid, typ, **kw):
    base = {"id": uid, "type": typ, "title": "카드 제목", "summary": "요약", "reason": "연결", "details": {"headline": "카드 제목",
            "coverage": "10월 28일 이후 기사 기준"}, "is_read": False, "created_at": T, "price_state": None,
            "observed_value": None, "observed_trade_date": None, "item_id": 7, "item_type": "topic",
            "item_description": "HBM 소식", "item_status": "active", "last_checked_at": T, "memo_id": 3, "memo_title": "메모",
            "color": "green", "symbol": "005930", "stock_name": "삼성전자", "memo_version": 2, "snapshot_title": "메모",
            "snapshot_body": "본문", "snapshot_at": T}
    base.update(kw)
    return base


class FakeRepo:
    def __init__(self, rows):
        self.rows = rows

    def cards(self, user_id, **kw):
        rows = self.rows
        if kw.get("unread_only"):
            rows = [r for r in rows if not r["is_read"]]
        return rows

    def sources(self, ids):
        return {1: [{"update_id": 1, "news_id": 55, "disclosure_rcept_no": None, "quote": "근거", "news_title": "기사 제목",
                     "news_url": "https://news.example/a", "published_at": T, "news_source": "한국경제",
                     "disclosure_title": None, "rcept_dt": None}],
                4: [{"update_id": 4, "news_id": None, "disclosure_rcept_no": "R1", "quote": "[청크 0] 배당", "news_title": None,
                     "news_url": None, "published_at": None, "news_source": None, "disclosure_title": "현금배당결정",
                     "rcept_dt": date(2026, 10, 29)}]}

    def recent_closes(self, symbol, until, n=10):
        return [(date(2026, 11, 6), 69000.0), (date(2026, 11, 7), 70500.0), (date(2026, 11, 10), 71000.0)]

    def similarities(self, pairs):
        return {(7, 55): 0.71}

    def memo(self, user_id, memo_id):
        return {"id": 3, "title": "메모", "ai_linked": True, "ai_linked_at": datetime(2026, 11, 1, tzinfo=timezone.utc),
                "symbol": "005930"} if memo_id == 3 else None

    def revisions(self, memo_id):
        return [{"revision_no": 1, "title": "메모", "content": "처음", "created_at": datetime(2026, 10, 30, tzinfo=timezone.utc)},
                {"revision_no": 2, "title": "메모", "content": "본문", "created_at": datetime(2026, 11, 2, tzinfo=timezone.utc)}]

    def items(self, memo_id):
        return [{"id": 7, "type": "topic", "description": "HBM 소식", "status": "active", "price_threshold": None,
                 "last_checked_at": T},
                {"id": 8, "type": "price_below", "description": "7만원 아래로", "status": "paused", "price_threshold": 70000,
                 "last_checked_at": None}]

    def mark_read(self, user_id, update_id):
        return update_id == 1

    def mark_memo_read(self, user_id, memo_id):
        if self.memo(user_id, memo_id) is None:
            return None
        hit = [r for r in self.rows if r["memo_id"] == memo_id and not r["is_read"]]
        for r in hit:
            r["is_read"] = True
        return len(hit)


ROWS = [card(1, "news"), card(2, "price_condition", title="조건가에 도달했어요", price_state="reached", observed_value=71000,
                               item_type="price_above", price_threshold=70000,
                               observed_trade_date=date(2026, 11, 10), is_read=True),
        card(4, "disclosure", memo_id=5, symbol="105560", stock_name="KB금융")]


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.s = UpdatesService(FakeRepo(ROWS))

    def test_ai_update_shape(self):
        news, price, disc = self.s.stock_ai_updates(1, "005930")
        self.assertEqual((news["type"], news["title"], news["headline"], news["source"], news["relevance"]),
                         ("news", "기사 제목", "카드 제목", "한국경제", 0.71))
        self.assertEqual(news["card"]["coverage"], "10월 28일 이후 기사 기준")
        self.assertEqual(news["item"]["last_checked_at"], T)
        self.assertEqual((price["type"], price["title"], price["source"], price["read"]), ("price", "종가 71,000원", "KRX", True))
        self.assertEqual(price["price"], {"state": "reached", "observed_value": 71000.0, "observed_trade_date": date(2026, 11, 10),
                                          "threshold": 70000.0, "direction": "above", "closes": [69000.0, 70500.0, 71000.0],
                                          "closes_from": date(2026, 11, 6)})
        self.assertEqual((news["memo_color"], news["price"]), ("green", None))
        self.assertEqual((disc["source"], disc["url"], disc["relevance"]),
                         ("DART", "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=R1", 1.0))
        for key in ("id", "stock_code", "stock_name", "type", "title", "source", "url", "published_at", "memo_id",
                    "memo_title", "memo_version", "summary", "headline", "read", "relevance"):
            self.assertIn(key, news)                                            # 계약 필드는 모두 있다

    def test_timeline(self):
        t = self.s.memo_timeline(1, 3)
        self.assertEqual([e["kind"] for e in t["entries"]], ["update", "update", "update", "memo_edit", "ai_linked", "memo_created"])
        self.assertEqual(t["entries"][0]["memo_snapshot"]["version"], 2)
        self.assertEqual(t["price_condition_count"], 1)
        self.assertEqual([i["last_checked_at"] for i in t["tracking_items"]], [T, None])
        with self.assertRaises(MemoNotFoundError):
            self.s.memo_timeline(1, 99)

    def test_summary_unread_only(self):
        out = self.s.summary(1)
        self.assertEqual([(s["stock_code"], s["new_count"]) for s in out], [("005930", 1), ("105560", 1)])
        self.assertEqual(out[0]["memos"][0]["color"], "green")
        with self.assertRaises(UpdateNotFoundError):
            self.s.mark_read(1, 2)

    def test_mark_memo_read(self):
        rows = [dict(r) for r in ROWS]
        s = UpdatesService(FakeRepo(rows))
        self.assertEqual(s.mark_memo_read(1, 3), 1)                    # 메모 3의 안 읽은 카드(1번)만 읽음으로
        self.assertEqual([r["is_read"] for r in rows], [True, True, False])  # 다른 메모(5) 카드는 그대로
        self.assertEqual(s.mark_memo_read(1, 3), 0)                    # 다시 불러도 괜찮음
        with self.assertRaises(MemoNotFoundError):
            s.mark_memo_read(1, 99)


class RouteTest(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        svc = UpdatesService(FakeRepo([dict(r) for r in ROWS]))
        app.dependency_overrides[get_current_user] = lambda: {"id": 1}
        app.dependency_overrides[get_query_service] = lambda: svc
        app.dependency_overrides[get_command_service] = lambda: svc
        self.c = TestClient(app)

    def test_routes(self):
        self.assertEqual(self.c.get("/api/v1/stocks/005930/ai-updates").status_code, 200)
        self.assertEqual(len(self.c.get("/api/v1/stocks/005930/ai-updates").json()), 3)
        self.assertEqual(self.c.get("/api/v1/memos/3/timeline").status_code, 200)
        self.assertEqual(self.c.get("/api/v1/memos/99/timeline").status_code, 404)
        self.assertEqual(self.c.get("/api/v1/ai-updates/summary").status_code, 200)
        self.assertEqual(self.c.post("/api/v1/ai-updates/1/read").status_code, 204)
        self.assertEqual(self.c.post("/api/v1/ai-updates/2/read").status_code, 404)
        self.assertEqual(self.c.post("/api/v1/memos/3/ai-updates/read").status_code, 204)
        self.assertEqual(self.c.post("/api/v1/memos/99/ai-updates/read").status_code, 404)


if __name__ == "__main__":
    unittest.main()
