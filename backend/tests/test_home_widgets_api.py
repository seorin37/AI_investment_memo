"""홈 위젯 API 테스트: /checklist-items, /price-conditions, /updates, 체크리스트 고정 (중앙 DB 없이)."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_auth_service, get_current_user
from app.board.service import BoardService, InvalidBoardPatchError
from app.home.routes import get_home_command_service, get_home_query_service, router as home_router
from app.home.service import HomeService
from app.updates.routes import get_query_service as get_updates_query_service
from app.updates.routes import router as updates_router
from app.updates.service import UpdatesService

T = datetime(2026, 11, 20, 1, 0, tzinfo=timezone.utc)


# ─── 가짜 저장소
class FakeHomeRepo:
    db = None

    def __init__(self):
        self.items = [
            {"id": 11, "label": "실적 발표일 확인", "is_done": False, "checklist_id": 5, "is_pinned": True,
             "stock_code": "000660", "stock_name": "SK하이닉스"},
            {"id": 12, "label": "컨센서스 비교", "is_done": True, "checklist_id": 5, "is_pinned": True,
             "stock_code": "000660", "stock_name": "SK하이닉스"},
        ]
        self.checklists = {("000660",): 5}
        self.appended: list[tuple[int, str]] = []
        self.memos = [
            {"id": 3, "title": "7만원 아래면 분할 매수", "ai_linked": True, "stock_code": "005930",
             "stock_name": "삼성전자", "current_price": Decimal("196900.00")},
            {"id": 4, "title": "주제 메모", "ai_linked": True, "stock_code": "005930",
             "stock_name": "삼성전자", "current_price": Decimal("196900.00")},
        ]
        self.notes = {3: {"id": 3, "ai_linked": True}, 9: {"id": 9, "ai_linked": False}}
        self.statuses: dict[int, str] = {}

    def checklist_items(self, user_id):
        return self.items

    def first_checklist(self, user_id, symbol):
        return self.checklists.get((symbol,))

    def append_checklist_item(self, checklist_id, label):
        self.appended.append((checklist_id, label))
        return 100 + len(self.appended)

    def price_condition_memos(self, user_id):
        return self.memos

    def owned_note(self, user_id, memo_id):
        return self.notes.get(memo_id)

    def set_item_status(self, memo_id, item_id, status):
        self.statuses[item_id] = status
        return True


class FakeTracking:
    conditions = {
        3: [{"id": "31", "direction": "below", "price": 70000, "tracking": True, "status": "waiting", "reached_at": None}],
        4: [],
        9: [{"id": "91", "direction": "above", "price": 90000, "tracking": False, "status": "paused", "reached_at": None}],
    }

    def price_conditions(self, memo_id):
        return self.conditions.get(memo_id, [])

    def stock_name(self, symbol):
        return {"000660": "SK하이닉스", "035420": "네이버"}.get(symbol, symbol)


class FakeBoardRepo:
    def __init__(self, owned):
        self.owned = owned

    def owns_stock(self, user_id, symbol):
        return symbol in self.owned


class FakeBoard:
    def __init__(self, owned):
        self.repository = FakeBoardRepo(owned)
        self.created: list[str] = []

    def create_checklist(self, user_id, symbol, payload):
        self.created.append((symbol, payload.title, payload.items))
        return {"id": "77"}


def _client(router, overrides):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "7"}
    app.dependency_overrides.update(overrides)
    return TestClient(app)


class HomeWidgetsTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeHomeRepo()
        self.board = FakeBoard({"000660", "035420"})
        service = HomeService(self.repo, tracking=FakeTracking(), board=self.board)
        self.client = _client(
            home_router, {get_home_query_service: lambda: service, get_home_command_service: lambda: service}
        )

    def test_checklist_items_shape(self):
        res = self.client.get("/api/v1/checklist-items")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json()[0],
            {"id": "11", "checklist_id": "5", "text": "실적 발표일 확인", "done": False,
             "stock_code": "000660", "stock_name": "SK하이닉스"},
        )

    def test_add_item_to_existing_checklist(self):
        res = self.client.post("/api/v1/checklist-items", json={"stock_code": "000660", "text": "  공시 보기 "})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(
            res.json(),
            {"id": "101", "checklist_id": "5", "text": "공시 보기", "done": False,
             "stock_code": "000660", "stock_name": "SK하이닉스"},
        )
        self.assertEqual(self.board.created, [])

    def test_add_item_creates_checklist_when_missing(self):
        res = self.client.post("/api/v1/checklist-items", json={"stock_code": "035420", "text": "광고 매출 확인"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["checklist_id"], "77")
        self.assertEqual(self.board.created, [("035420", "체크리스트", [])])
        self.assertEqual(self.repo.appended, [(77, "광고 매출 확인")])

    def test_add_item_validation(self):
        self.assertEqual(self.client.post("/api/v1/checklist-items", json={"stock_code": "999999", "text": "x"}).status_code, 404)
        self.assertEqual(self.client.post("/api/v1/checklist-items", json={"stock_code": "000660", "text": "  "}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/checklist-items", json={"stock_code": "abc", "text": "x"}).status_code, 422)

    def test_price_conditions_shape(self):
        res = self.client.get("/api/v1/price-conditions")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json(),
            [{"memo_id": "3", "memo_title": "7만원 아래면 분할 매수", "stock_code": "005930", "stock_name": "삼성전자",
              "condition": FakeTracking.conditions[3][0], "current_price": 196900}],
        )

    def test_set_price_tracking(self):
        url = "/api/v1/memos/3/price-conditions/31"
        self.assertEqual(self.client.patch(url, json={"tracking": False}).status_code, 204)
        self.assertEqual(self.repo.statuses, {31: "paused"})
        self.assertEqual(self.client.patch(url, json={"tracking": True}).status_code, 204)
        self.assertEqual(self.repo.statuses, {31: "active"})

    def test_set_price_tracking_errors(self):
        self.assertEqual(self.client.patch("/api/v1/memos/3/price-conditions/99", json={"tracking": True}).status_code, 404)
        self.assertEqual(self.client.patch("/api/v1/memos/8/price-conditions/31", json={"tracking": True}).status_code, 404)
        # AI 연결이 꺼진 메모는 켤 수 없고, 끄기는 된다
        self.assertEqual(self.client.patch("/api/v1/memos/9/price-conditions/91", json={"tracking": True}).status_code, 409)
        self.assertEqual(self.client.patch("/api/v1/memos/9/price-conditions/91", json={"tracking": False}).status_code, 204)
        self.assertEqual(self.client.patch("/api/v1/memos/3/price-conditions/31", json={}).status_code, 422)

    def test_requires_authentication(self):
        app = FastAPI()
        app.include_router(home_router)
        app.dependency_overrides[get_auth_service] = lambda: None
        app.dependency_overrides[get_home_query_service] = lambda: None
        app.dependency_overrides[get_home_command_service] = lambda: None
        client = TestClient(app)
        self.assertEqual(client.get("/api/v1/checklist-items").status_code, 401)
        self.assertEqual(client.get("/api/v1/price-conditions").status_code, 401)
        self.assertEqual(client.post("/api/v1/checklist-items", json={"stock_code": "000660", "text": "x"}).status_code, 401)


# ─── /updates
def card(uid, typ, **kw):
    base = {"id": uid, "type": typ, "title": "카드 제목", "summary": "요약", "reason": "연결", "details": {},
            "is_read": False, "created_at": T, "price_state": None, "observed_value": None, "observed_trade_date": None,
            "item_id": 7, "item_type": "topic", "item_description": "HBM 소식", "item_status": "active",
            "last_checked_at": T, "memo_id": 3, "memo_title": "메모", "color": "green", "symbol": "005930",
            "stock_name": "삼성전자", "memo_version": 1, "snapshot_title": "메모", "snapshot_body": "본문", "snapshot_at": T}
    base.update(kw)
    return base


NEWS_SRC = {"update_id": 1, "news_id": 55, "disclosure_rcept_no": None, "quote": "근거", "news_title": "기사 제목",
            "news_url": "https://news.example/a", "published_at": T, "news_source": "한국경제",
            "disclosure_title": None, "rcept_dt": None}


class FakeUpdatesRepo:
    def __init__(self):
        self.calls = []
        self.rows = [
            card(1, "news"),
            card(2, "news", memo_id=4, memo_title="다른 메모"),          # 같은 기사, 다른 메모 → 하나로
            card(3, "answer", item_type="ask"),
            card(5, "price_condition", title="조건가 도달", price_state="reached", observed_value=Decimal("71000"),
                 observed_trade_date=date(2026, 11, 19)),
        ]

    def cards(self, user_id, **kw):
        self.calls.append(kw)
        return self.rows

    def sources(self, ids):
        return {1: [NEWS_SRC], 2: [{**NEWS_SRC, "update_id": 2}], 3: [{**NEWS_SRC, "update_id": 3, "news_id": 56,
                                                                       "news_url": "https://news.example/b",
                                                                       "news_title": "답 근거 기사"}]}

    def recent_closes(self, symbol, until, n=10):
        return []

    def similarities(self, pairs):
        return {}


class MarketUpdatesTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeUpdatesRepo()
        service = UpdatesService(self.repo)
        self.client = _client(updates_router, {get_updates_query_service: lambda: service})

    def test_feed_shape_dedup_and_answer_type(self):
        res = self.client.get("/api/v1/updates")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual([(u["id"], u["type"]) for u in body], [("1", "news"), ("3", "news"), ("5", "price")])
        for key in ("id", "stock_code", "stock_name", "type", "title", "source", "url", "published_at"):
            self.assertIn(key, body[0])
        self.assertEqual(body[2]["title"], "종가 71,000원")
        self.assertEqual(self.repo.calls[0], {"symbol": None, "ai_linked_only": False, "active_stocks_only": True,
                                              "recent_days": 30, "limit": 500})

    def test_feed_params(self):
        self.assertEqual(len(self.client.get("/api/v1/updates", params={"limit": 1}).json()), 1)
        self.client.get("/api/v1/updates", params={"stock_code": "005930"})
        self.assertEqual(self.repo.calls[-1]["symbol"], "005930")
        self.assertEqual(self.client.get("/api/v1/updates", params={"stock_code": "x"}).status_code, 422)


# ─── 체크리스트 고정
class FakeBoardRepoForPin:
    db = None

    def __init__(self):
        now = T
        self.row = {"id": 5, "symbol": "000660", "kind": "checklist", "title": "체크", "content": "", "is_pinned": False,
                    "position": 1, "created_at": now, "updated_at": now, "user_id": 7}
        self.order = [{"id": 4, "pinned": False}, {"id": 5, "pinned": False}]
        self.written = []

    def get_owned(self, user_id, memo_id):
        return dict(self.row) if memo_id == 5 else None

    def owns_stock(self, user_id, symbol):
        return True

    def update_base(self, user_id, memo_id, base):
        if "pinned" in base:
            self.row["is_pinned"] = base["pinned"]
        return True

    def board_order(self, user_id, symbol, lock=False):
        return self.order

    def write_order(self, user_id, symbol, ids):
        self.written.append(ids)

    def checklist_items(self, memo_id):
        return []


class ChecklistPinTest(unittest.TestCase):
    def test_checklist_can_be_pinned_and_response_has_pinned(self):
        repo = FakeBoardRepoForPin()
        service = BoardService(repo, tracking=FakeTracking(), llm_factory=lambda: None)
        out = service.update(7, 5, {"pinned": True})
        self.assertTrue(out["pinned"])
        self.assertEqual(repo.written, [[5, 4]])                  # 테이프 붙이면 맨 앞

    def test_reference_still_rejects_pinned(self):
        repo = FakeBoardRepoForPin()
        repo.row["kind"] = "reference"
        service = BoardService(repo, tracking=FakeTracking(), llm_factory=lambda: None)
        with self.assertRaises(InvalidBoardPatchError):
            service.update(7, 5, {"pinned": True})


if __name__ == "__main__":
    unittest.main()
