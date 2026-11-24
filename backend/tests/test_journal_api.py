"""투자 기록 API (0020 journal_entries.blocks). DB 없이 — 0020 적용 전에도 돈다."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import ProgrammingError

from app.auth.routes import get_auth_service, get_current_user
from app.journal.markdown import blocks_to_markdown
from app.journal.routes import get_journal_command_service, get_journal_query_service, router
from app.journal.service import JournalService
from app.trash.routes import get_trash_command_service, get_trash_query_service, router as trash_router
from app.trash.service import TrashService

T0 = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
STOCKS = {"000660": "SK하이닉스", "005930": "삼성전자"}


class FakeJournalRepo:
    """journal_entries + journal_entry_stocks 를 메모리로 (사용자별)."""

    def __init__(self):
        self.rows: dict[int, dict] = {}
        self.stocks: dict[int, list[str]] = {}
        self.next_id = 1
        self.clock = T0

    def _tick(self):
        self.clock += timedelta(minutes=1)
        return self.clock

    def _view(self, row):
        symbols = sorted(self.stocks.get(row["id"], []))
        code = symbols[0] if symbols else None
        return {**row, "stock_code": code, "stock_name": STOCKS.get(code) if code else None}

    def list(self, user_id, limit=500):
        rows = [r for r in self.rows.values() if r["user_id"] == user_id and r["deleted_at"] is None]
        return [self._view(r) for r in sorted(rows, key=lambda r: (r["created_at"], r["id"]), reverse=True)][:limit]

    def get(self, user_id, entry_id):
        r = self.rows.get(entry_id)
        return self._view(r) if r and r["user_id"] == user_id and r["deleted_at"] is None else None

    def stock_exists(self, symbol):
        return symbol in STOCKS

    def create(self, user_id, *, title, body, blocks, pinned=False):
        now = self._tick()
        entry_id, self.next_id = self.next_id, self.next_id + 1
        self.rows[entry_id] = {"id": entry_id, "user_id": user_id, "title": title, "body": body, "blocks": blocks,
                               "is_pinned": pinned,
                               "created_at": now, "updated_at": now, "deleted_at": None, "source_memo_id": None,
                               "kind": None, "status": "draft", "folder_id": None, "parent_id": None}
        return entry_id

    def update(self, user_id, entry_id, values, *, touch=True):
        r = self.rows.get(entry_id)
        if not r or r["user_id"] != user_id or r["deleted_at"] is not None:
            return False
        r.update(values)
        if touch:
            r["updated_at"] = self._tick()
        return True

    def set_stock(self, entry_id, symbol):
        self.stocks[entry_id] = [symbol] if symbol else []

    def soft_delete(self, user_id, entry_id):
        r = self.rows.get(entry_id)
        if not r or r["user_id"] != user_id or r["deleted_at"] is not None:
            return False
        r["deleted_at"] = self._tick()
        return True


class FakeTrashForJournal:
    """TrashService 가 부르는 저장소: 투자 기록만 FakeJournalRepo 에 이어 붙인다."""

    def __init__(self, journal: FakeJournalRepo):
        self.j = journal

    def deleted_memos(self, user_id):
        return []

    def deleted_stocks(self, user_id):
        return []

    def deleted_studio(self, user_id):
        return []

    def deleted_journals(self, user_id):
        return [{"id": r["id"], "title": r["title"], "content": r["body"], "deleted_at": r["deleted_at"]}
                for r in self.j.rows.values() if r["user_id"] == user_id and r["deleted_at"] is not None]

    def restore_journal(self, user_id, entry_id):
        r = self.j.rows.get(entry_id)
        if not r or r["user_id"] != user_id or r["deleted_at"] is None:
            return False
        r["deleted_at"] = None
        return True

    def purge_journal(self, user_id, entry_id):
        r = self.j.rows.get(entry_id)
        if not r or r["user_id"] != user_id or r["deleted_at"] is None:
            return False
        self.j.stocks.pop(entry_id, None)
        del self.j.rows[entry_id]
        return True


BLOCKS = [
    {"id": "b1", "type": "paragraph", "text": "오늘 반도체 업종이 강세였다.\n추격 매수는 안 했다."},
    {"id": "b2", "type": "heading", "text": "다음 액션", "highlight": True},
    {"id": "b3", "type": "checklist", "text": "실적 발표일 확인", "checked": True},
    {"id": "b4", "type": "checklist", "text": "분할 매수 계획", "checked": False},
    {"id": "b5", "type": "table", "rows": [["항목", "값"], ["PER", "14 | 업종 평균"]]},
    {"id": "b6", "type": "attachment", "name": "IR 자료.pdf", "url": "https://example.com/ir.pdf"},
    {"id": "b7", "type": "paragraph", "text": ""},
]


class MarkdownTest(unittest.TestCase):
    def test_blocks_to_markdown(self):
        self.assertEqual(
            blocks_to_markdown(BLOCKS),
            "오늘 반도체 업종이 강세였다.\n추격 매수는 안 했다.\n\n"
            "## ==다음 액션==\n\n"
            "- [x] 실적 발표일 확인\n- [ ] 분할 매수 계획\n\n"
            "| 항목 | 값 |\n|---|---|\n| PER | 14 \\| 업종 평균 |\n\n"
            "[IR 자료.pdf](https://example.com/ir.pdf)",
        )

    def test_empty(self):
        self.assertEqual(blocks_to_markdown([]), "")


class JournalApiTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeJournalRepo()
        service = JournalService(self.repo)
        app = FastAPI()
        app.include_router(router)
        app.include_router(trash_router)
        app.dependency_overrides[get_current_user] = lambda: {"id": "7"}
        app.dependency_overrides[get_journal_query_service] = lambda: service
        app.dependency_overrides[get_journal_command_service] = lambda: service
        trash = TrashService(FakeTrashForJournal(self.repo))
        app.dependency_overrides[get_trash_query_service] = lambda: trash
        app.dependency_overrides[get_trash_command_service] = lambda: trash
        self.client = TestClient(app)

    def _create(self, **kw):
        body = {"title": "10/13 투자 복기", "stock_code": "000660", "blocks": BLOCKS, **kw}
        res = self.client.post("/api/v1/journal", json=body)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def test_create_matches_mock_shape_and_stores_markdown(self):
        e = self._create()
        self.assertEqual(set(e), {"id", "title", "stock_code", "stock_name", "blocks", "pinned", "created_at", "updated_at"})
        self.assertIs(e["pinned"], False)
        self.assertEqual((e["title"], e["stock_code"], e["stock_name"]), ("10/13 투자 복기", "000660", "SK하이닉스"))
        self.assertEqual(e["blocks"], [{k: v for k, v in b.items()} for b in BLOCKS])     # 원본 그대로 (id·강조 포함)
        row = self.repo.rows[int(e["id"])]
        self.assertEqual(row["body"], blocks_to_markdown(BLOCKS))
        self.assertIsNone(row["source_memo_id"])                                         # 메모와 연결하지 않음
        self.assertEqual((row["kind"], row["status"], row["folder_id"], row["parent_id"]), (None, "draft", None, None))

    def test_list_newest_first(self):
        first = self._create(title="첫 기록")
        second = self._create(title="둘째 기록", stock_code=None)
        body = self.client.get("/api/v1/journal").json()
        self.assertEqual([e["id"] for e in body], [second["id"], first["id"]])
        self.assertEqual((body[0]["stock_code"], body[0]["stock_name"]), (None, None))

    def test_patch_title_blocks_and_stock(self):
        e = self._create()
        res = self.client.patch(f"/api/v1/journal/{e['id']}", json={"blocks": [{"id": "x", "type": "paragraph", "text": "고침"}]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["blocks"], [{"id": "x", "type": "paragraph", "text": "고침"}])
        self.assertEqual(self.repo.rows[int(e["id"])]["body"], "고침")
        self.assertEqual(res.json()["stock_code"], "000660")                              # 안 보낸 칸은 그대로
        self.assertEqual(res.json()["title"], "10/13 투자 복기")
        res = self.client.patch(f"/api/v1/journal/{e['id']}", json={"stock_code": "005930", "title": "새 제목"})
        self.assertEqual((res.json()["stock_code"], res.json()["stock_name"], res.json()["title"]),
                         ("005930", "삼성전자", "새 제목"))
        res = self.client.patch(f"/api/v1/journal/{e['id']}", json={"stock_code": None})   # null = 종목 연결 해제
        self.assertEqual((res.json()["stock_code"], res.json()["stock_name"]), (None, None))
        self.assertGreater(res.json()["updated_at"], e["updated_at"])

    def test_line_formats_are_kept_and_go_to_markdown(self):
        """화면 서식(작은 제목 · 목록 · 굵게/기울임/밑줄/취소선)이 저장되고 그대로 돌아온다."""
        blocks = [
            {"id": "a", "type": "heading", "text": "작은 제목", "level": 2},
            {"id": "b", "type": "paragraph", "text": "하나", "list_style": "dot", "bold": True},
            {"id": "c", "type": "paragraph", "text": "둘", "list_style": "dot"},
            {"id": "d", "type": "paragraph", "text": "인용", "list_style": "quote", "italic": True},
            {"id": "e", "type": "checklist", "text": "할 일", "checked": False, "strike": True, "underline": True},
        ]
        e = self._create(blocks=blocks, stock_code=None)
        self.assertEqual(e["blocks"], blocks)
        self.assertEqual(self.repo.rows[int(e["id"])]["body"],
                         "### 작은 제목\n\n- **하나**\n- 둘\n\n> *인용*\n\n- [ ] ~~할 일~~")
        bad = [{"id": "x", "type": "paragraph", "text": "t", "list_style": "star"}]
        self.assertEqual(self.client.post("/api/v1/journal", json={"blocks": bad}).status_code, 422)
        bad = [{"id": "x", "type": "heading", "text": "t", "level": 3}]
        self.assertEqual(self.client.post("/api/v1/journal", json={"blocks": bad}).status_code, 422)
        bad = [{"id": "x", "type": "paragraph", "text": "t", "color": "red"}]           # 모르는 칸은 여전히 거절
        self.assertEqual(self.client.post("/api/v1/journal", json={"blocks": bad}).status_code, 422)

    def test_pin_keeps_edited_date(self):
        e = self._create(stock_code=None)
        res = self.client.patch(f"/api/v1/journal/{e['id']}", json={"pinned": True})
        self.assertEqual(res.status_code, 200)
        self.assertIs(res.json()["pinned"], True)
        self.assertEqual(res.json()["updated_at"], e["updated_at"])                       # 고정은 고친 날을 안 바꿈
        self.assertIs(self.client.get("/api/v1/journal").json()[0]["pinned"], True)
        res = self.client.patch(f"/api/v1/journal/{e['id']}", json={"title": "고침"})
        self.assertIs(res.json()["pinned"], True)                                         # 다른 칸을 고쳐도 고정 유지
        self.assertGreater(res.json()["updated_at"], e["updated_at"])
        created = self._create(stock_code=None, pinned=True)
        self.assertIs(created["pinned"], True)

    def test_validation(self):
        self.assertEqual(self.client.post("/api/v1/journal", json={"title": "x", "stock_code": "999999"}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/journal", json={"blocks": [{"id": "b", "type": "video"}]}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/journal", json={"blocks": [{"type": "paragraph", "text": "id 없음"}]}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/journal", json={"title": "x", "source_memo_id": 1}).status_code, 422)
        self.assertEqual(self.client.patch("/api/v1/journal/999", json={"title": "x"}).status_code, 404)

    def test_delete_goes_to_trash_and_restore_purge(self):
        e = self._create(title="")
        self.assertEqual(self.client.delete(f"/api/v1/journal/{e['id']}").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/journal").json(), [])
        self.assertEqual(self.client.delete(f"/api/v1/journal/{e['id']}").status_code, 404)
        trash = self.client.get("/api/v1/trash").json()
        self.assertEqual([(t["id"], t["kind"], t["title"], t["context"]) for t in trash],
                         [(f"journal-{e['id']}", "journal", "제목 없는 기록", "투자 기록")])
        self.assertEqual(self.client.post(f"/api/v1/trash/journal-{e['id']}/restore").status_code, 204)
        self.assertEqual(len(self.client.get("/api/v1/journal").json()), 1)
        self.client.delete(f"/api/v1/journal/{e['id']}")
        self.assertEqual(self.client.delete(f"/api/v1/trash/journal-{e['id']}").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/trash").json(), [])
        self.assertEqual(self.client.post(f"/api/v1/trash/journal-{e['id']}/restore").status_code, 404)

    def test_legacy_row_without_blocks_shows_body_as_paragraph(self):
        e = self._create()
        row = self.repo.rows[int(e["id"])]
        row["blocks"], row["body"] = None, "예전 본문"
        self.assertEqual(self.client.get("/api/v1/journal").json()[0]["blocks"],
                         [{"id": f"b{e['id']}", "type": "paragraph", "text": "예전 본문"}])

    def test_before_migration_0020_returns_503(self):
        class NoBlocksColumn(FakeJournalRepo):
            def list(self, user_id, limit=500):
                raise ProgrammingError("SELECT e.blocks", {}, Exception('column e.blocks does not exist'))

        service = JournalService(NoBlocksColumn())
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"id": "7"}
        app.dependency_overrides[get_journal_query_service] = lambda: service
        res = TestClient(app).get("/api/v1/journal")
        self.assertEqual(res.status_code, 503)
        self.assertIn("0020", res.json()["detail"])

    def test_requires_authentication(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_service] = lambda: None
        app.dependency_overrides[get_journal_query_service] = lambda: None
        app.dependency_overrides[get_journal_command_service] = lambda: None
        client = TestClient(app)
        self.assertEqual(client.get("/api/v1/journal").status_code, 401)
        self.assertEqual(client.post("/api/v1/journal", json={}).status_code, 401)
        self.assertEqual(client.delete("/api/v1/journal/1").status_code, 401)


if __name__ == "__main__":
    unittest.main()
