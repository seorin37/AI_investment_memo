"""Memo-board API contract tests without DB or external services."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth.routes import get_current_user
from app.board.routes import get_command_service, get_query_service, router
from app.board.service import BoardItemNotFoundError, InvalidBoardPatchError


class FakeBoardService:
    def __init__(self) -> None:
        self.rows: dict[tuple[int, int], dict] = {}
        self.next_id = 1

    def _common(self, kind: str, code: str, title: str) -> dict:
        now = datetime(2026, 11, 5, tzinfo=timezone.utc)
        result = {
            "id": str(self.next_id), "kind": kind, "stock_code": code,
            "title": title, "position": len(self.rows), "created_at": now, "updated_at": now,
        }
        self.next_id += 1
        return result

    def list_board(self, user_id: int, symbol: str):
        return [row for (owner, _), row in self.rows.items() if owner == user_id and row["stock_code"] == symbol]

    def get(self, user_id: int, memo_id: int):
        try:
            return self.rows[(user_id, memo_id)]
        except KeyError as exc:
            raise BoardItemNotFoundError(memo_id) from exc

    def create_memo(self, user_id: int, symbol: str, payload):
        row = {
            **self._common("memo", symbol, payload.title), "body": payload.body,
            "tags": payload.tags, "color": payload.color, "pinned": payload.pinned,
            "ai_linked": payload.ai_linked, "ai_linked_at": None,
            "price_conditions": [], "unread_updates": 0,
        }
        self.rows[(user_id, int(row["id"]))] = row
        return row

    def create_checklist(self, user_id: int, symbol: str, payload):
        row = {**self._common("checklist", symbol, payload.title), "items": [
            {"id": str(index + 1), "text": item.text, "done": item.done}
            for index, item in enumerate(payload.items)
        ]}
        self.rows[(user_id, int(row["id"]))] = row
        return row

    def create_reference(self, user_id: int, symbol: str, payload):
        row = {**self._common("reference", symbol, payload.title), "links": [
            {"id": str(index + 1), "title": link.title, "url": str(link.url),
             "ref_type": link.ref_type, "source": link.source}
            for index, link in enumerate(payload.links)
        ]}
        self.rows[(user_id, int(row["id"]))] = row
        return row

    def update(self, user_id: int, memo_id: int, values: dict):
        row = self.get(user_id, memo_id)
        values = dict(values)
        if "position" in values:
            row["position"] = values.pop("position")
            if not values:
                return row
        allowed = {
            "memo": {"title", "body", "tags", "color", "pinned"},
            "checklist": {"title", "items"},
            "reference": {"title", "links"},
        }[row["kind"]]
        if set(values) - allowed:
            raise InvalidBoardPatchError("invalid fields")
        if "links" in values:
            values["links"] = [
                {
                    "id": str(index + 1),
                    "title": link["title"],
                    "url": str(link["url"]),
                    "ref_type": link["ref_type"],
                    "source": link["source"],
                }
                for index, link in enumerate(values["links"])
            ]
        row.update(values)
        return row

    def update_checklist_item(self, user_id: int, memo_id: int, item_id: int, values: dict):
        row = self.get(user_id, memo_id)
        for item in row["items"]:
            if int(item["id"]) == item_id:
                item.update(values)
                return row
        raise BoardItemNotFoundError(item_id)

    def set_ai_link(self, user_id: int, memo_id: int, enabled: bool):
        row = self.get(user_id, memo_id)
        if row["kind"] != "memo":
            raise InvalidBoardPatchError("일반 메모만 AI 추적 가능")
        row["ai_linked"] = enabled
        return row

    def reorder(self, user_id: int, symbol: str, ids: list[int]):
        mine = {int(row["id"]) for (owner, _), row in self.rows.items() if owner == user_id and row["stock_code"] == symbol}
        if len(set(ids)) != len(ids) or set(ids) - mine:
            raise InvalidBoardPatchError("bad order")
        for index, memo_id in enumerate(ids):
            self.rows[(user_id, memo_id)]["position"] = index
        return sorted(self.list_board(user_id, symbol), key=lambda row: row["position"])

    def delete(self, user_id: int, memo_id: int):
        if self.rows.pop((user_id, memo_id), None) is None:
            raise BoardItemNotFoundError(memo_id)


def _client():
    app = FastAPI()
    app.include_router(router)
    service = FakeBoardService()
    user = {"id": "1"}
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_query_service] = lambda: service
    app.dependency_overrides[get_command_service] = lambda: service
    return TestClient(app), service, user, app


def test_create_list_detail_update_and_delete_memo():
    client, _service, _user, _app = _client()
    created = client.post("/api/v1/stocks/005930/memos", json={
        "title": "투자 메모", "body": "본문", "tags": ["장기"], "color": "blue",
        "ai_linked": True, "pinned": True,
    })
    assert created.status_code == 201
    memo_id = created.json()["id"]
    assert client.get("/api/v1/stocks/005930/board").json()[0]["body"] == "본문"
    assert client.get(f"/api/v1/board-items/{memo_id}").status_code == 200
    updated = client.patch(f"/api/v1/board-items/{memo_id}", json={"body": "수정 본문"})
    assert updated.json()["body"] == "수정 본문"
    assert client.delete(f"/api/v1/board-items/{memo_id}").status_code == 204
    assert client.get(f"/api/v1/board-items/{memo_id}").status_code == 404


def test_checklist_create_and_item_completion():
    client, _service, _user, _app = _client()
    created = client.post("/api/v1/stocks/005930/checklists", json={
        "title": "확인", "items": [{"text": "실적 확인", "done": False}],
    })
    checklist_id = created.json()["id"]
    changed = client.patch(f"/api/v1/checklists/{checklist_id}/items/1", json={"done": True})
    assert changed.status_code == 200
    assert changed.json()["items"][0]["done"] is True
    assert client.put(f"/api/v1/memos/{checklist_id}/ai-link", json={"enabled": True}).status_code == 422


def test_reference_create_update_and_invalid_url():
    client, _service, _user, _app = _client()
    invalid = client.post("/api/v1/stocks/005930/references", json={
        "title": "자료", "links": [{"title": "bad", "url": "not-a-url"}],
    })
    assert invalid.status_code == 422
    created = client.post("/api/v1/stocks/005930/references", json={
        "title": "자료", "links": [{"title": "IR", "url": "https://example.com/ir", "ref_type": "ir"}],
    })
    assert created.status_code == 201
    memo_id = created.json()["id"]
    changed = client.patch(f"/api/v1/board-items/{memo_id}", json={
        "links": [{"title": "공시", "url": "https://example.com/disclosure", "ref_type": "disclosure"}],
    })
    assert changed.status_code == 200
    assert changed.json()["links"][0]["ref_type"] == "disclosure"


def test_user_isolation_and_cross_user_mutations_are_hidden_as_404():
    client, _service, user, _app = _client()
    memo_id = client.post("/api/v1/stocks/005930/memos", json={
        "title": "A 메모", "body": "private", "tags": [], "color": "yellow", "ai_linked": False,
    }).json()["id"]
    user["id"] = "2"
    assert client.get("/api/v1/stocks/005930/board").json() == []
    assert client.get(f"/api/v1/board-items/{memo_id}").status_code == 404
    assert client.patch(f"/api/v1/board-items/{memo_id}", json={"title": "침범"}).status_code == 404
    assert client.delete(f"/api/v1/board-items/{memo_id}").status_code == 404


def test_unauthenticated_and_invalid_patch_are_rejected():
    client, _service, _user, app = _client()
    app.dependency_overrides[get_current_user] = lambda: (_ for _ in ()).throw(
        HTTPException(401, detail="Not authenticated")
    )
    assert client.get("/api/v1/stocks/005930/board").status_code == 401

    app.dependency_overrides[get_current_user] = lambda: {"id": "1"}
    memo_id = client.post("/api/v1/stocks/005930/memos", json={
        "title": "메모", "body": "body", "tags": [], "color": "yellow", "ai_linked": False,
    }).json()["id"]
    assert client.patch(f"/api/v1/board-items/{memo_id}", json={"position": -1}).status_code == 422
    assert client.patch(f"/api/v1/board-items/{memo_id}", json={"items": []}).status_code == 422


def test_board_order_put_and_position_patch():
    client, _service, user, _app = _client()
    ids = [client.post("/api/v1/stocks/005930/memos", json={
        "title": f"메모 {n}", "body": "b", "tags": [], "color": "yellow", "ai_linked": False,
    }).json()["id"] for n in range(3)]
    reordered = client.put("/api/v1/stocks/005930/board-order", json={"ids": [int(ids[2]), int(ids[0]), int(ids[1])]})
    assert reordered.status_code == 200
    assert [row["id"] for row in reordered.json()] == [ids[2], ids[0], ids[1]]
    assert client.put("/api/v1/stocks/005930/board-order", json={"ids": [int(ids[0]), int(ids[0])]}).status_code == 422
    assert client.put("/api/v1/stocks/005930/board-order", json={"ids": ["x"]}).status_code == 422
    assert client.patch(f"/api/v1/board-items/{ids[1]}", json={"position": 0}).json()["position"] == 0
    user["id"] = "2"
    assert client.put("/api/v1/stocks/005930/board-order", json={"ids": [int(ids[0])]}).status_code == 422
