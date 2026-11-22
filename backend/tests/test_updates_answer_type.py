"""0019 질문 답(answer) 카드: 카드를 내보내는 네 API 모두 계약 type(disclosure|news|price)으로 보낸다."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_current_user
from app.updates.routes import get_query_service, router
from app.updates.service import UpdatesService, contract_type

T = datetime(2026, 11, 20, 6, 30, tzinfo=timezone.utc)
CONTRACT = {"disclosure", "news", "price"}


def card(uid, typ, **kw):
    base = {"id": uid, "type": typ, "title": "카드 제목", "summary": "요약", "reason": None, "details": {},
            "is_read": False, "created_at": T, "price_state": None, "observed_value": None, "observed_trade_date": None,
            "item_id": 7, "item_type": "topic", "item_description": "HBM 소식", "item_status": "active",
            "last_checked_at": T, "memo_id": 3, "memo_title": "메모", "color": "green", "symbol": "005930",
            "stock_name": "삼성전자", "memo_version": 1, "snapshot_title": "메모", "snapshot_body": "본문", "snapshot_at": T}
    base.update(kw)
    return base


NEWS = {"news_id": 55, "disclosure_rcept_no": None, "quote": "근거", "news_title": "기사", "news_url": "https://n/a",
        "published_at": T, "news_source": "한국경제", "disclosure_title": None, "rcept_dt": None}
DISC = {"news_id": None, "disclosure_rcept_no": "R1", "quote": "배당", "news_title": None, "news_url": None,
        "published_at": None, "news_source": None, "disclosure_title": "현금배당결정", "rcept_dt": date(2026, 11, 19)}

ROWS = [
    card(1, "news"),
    card(2, "answer", item_type="ask", details={"answer_status": "answer", "question": "배당 늘려?"}),   # 근거: 공시
    card(3, "answer", item_type="ask", details={"answer_status": "answer"}),                          # 근거: 뉴스
    card(4, "answer", item_type="ask", title="배당 늘려?", details={"answer_status": "no_answer"}),      # 근거 없음
    card(5, "price_condition", price_state="reached", observed_value=71000, observed_trade_date=date(2026, 11, 19)),
]
NEWS2 = {**NEWS, "news_id": 56, "news_title": "답 근거 기사", "news_url": "https://n/b"}
SOURCES = {1: [NEWS], 2: [DISC], 3: [NEWS2]}   # /updates 는 같은 기사 카드를 하나로 줄이므로 다른 기사로


class FakeRepo:
    def cards(self, user_id, **kw):
        return [r for r in ROWS if not kw.get("unread_only") or not r["is_read"]]

    def sources(self, ids):
        return {i: SOURCES[i] for i in ids if i in SOURCES}

    def recent_closes(self, symbol, until, n=10):
        return []

    def similarities(self, pairs):
        return {}

    def memo(self, user_id, memo_id):
        return {"id": 3, "title": "메모", "ai_linked": True, "ai_linked_at": T, "symbol": "005930"}

    def revisions(self, memo_id):
        return [{"revision_no": 1, "title": "메모", "content": "본문", "created_at": T}]

    def items(self, memo_id):
        return []


class ContractTypeTest(unittest.TestCase):
    def test_contract_type(self):
        self.assertEqual(contract_type("price_condition", []), "price")
        self.assertEqual(contract_type("news", [{"kind": "disclosure"}]), "news")
        self.assertEqual(contract_type("answer", [{"kind": "disclosure"}]), "disclosure")
        self.assertEqual(contract_type("answer", [{"kind": "news"}]), "news")
        self.assertEqual(contract_type("answer", []), "news")
        self.assertEqual(contract_type("something_new", []), "news")

    def test_all_four_apis_send_contract_types(self):
        service = UpdatesService(FakeRepo())
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"id": "1"}
        app.dependency_overrides[get_query_service] = lambda: service
        client = TestClient(app)

        stock = client.get("/api/v1/stocks/005930/ai-updates").json()
        timeline = [e["update"] for e in client.get("/api/v1/memos/3/timeline").json()["entries"] if e["kind"] == "update"]
        summary = [u for s in client.get("/api/v1/ai-updates/summary").json() for m in s["memos"] for u in m["updates"]]
        feed = client.get("/api/v1/updates").json()
        for name, updates in (("ai-updates", stock), ("timeline", timeline), ("summary", summary), ("updates", feed)):
            with self.subTest(api=name):
                self.assertTrue(updates)
                self.assertEqual({u["type"] for u in updates} - CONTRACT, set())
                by_id = {u["id"]: u for u in updates}
                self.assertEqual(by_id["2"]["type"], "disclosure")
                self.assertEqual(by_id["3"]["type"], "news")
                self.assertEqual((by_id["4"]["type"], by_id["4"]["answer_status"]), ("news", "no_answer"))
                self.assertEqual((by_id["2"]["card_type"], by_id["2"]["answer_status"]), ("answer", "answer"))
                self.assertEqual((by_id["1"]["card_type"], by_id["1"]["answer_status"]), ("news", None))
                self.assertEqual(by_id["5"]["type"], "price")


if __name__ == "__main__":
    unittest.main()
