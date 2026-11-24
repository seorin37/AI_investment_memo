"""스튜디오 만든 항목 (studio_items) 목록·삭제·실험실 저장 (2026-11-23). DB·LLM 없이 가짜 세션으로 확인한다."""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_current_user
from app.db import get_read_db
from app.studio_lab import items, routes
from tests.test_studio_lab import DIRS, GOOD, STOCK, fake

NOW = datetime(2026, 11, 23, 3, 0, tzinfo=timezone.utc)


class FakeDb:
    """studio_items 한 테이블만 흉내 낸다 (SQL 문 앞부분으로 구분)."""

    def __init__(self, rows=None, fail_insert=False):
        self.rows = list(rows or [])
        self.fail_insert = fail_insert

    def execute(self, stmt, params):
        sql = str(stmt).lstrip()
        if sql.startswith("SELECT"):
            mine = [r for r in self.rows if r["user_id"] == params["uid"] and r["expires_at"] > NOW and r.get("deleted_at") is None]
            mine.sort(key=lambda r: (r["created_at"], r["id"]), reverse=True)
            return _Result(rows=mine)
        if sql.startswith("UPDATE"):                          # 삭제 = 휴지통 (deleted_at, 0025)
            hit = [r for r in self.rows if r["id"] == params["id"] and r["user_id"] == params["uid"]
                   and r.get("deleted_at") is None and r["expires_at"] > NOW]
            for r in hit:
                r["deleted_at"] = NOW
            return _Result(rowcount=len(hit))
        if sql.startswith("INSERT"):
            if self.fail_insert:
                raise RuntimeError("db down")
            new_id = max([r["id"] for r in self.rows] or [0]) + 1
            self.rows.append({"id": new_id, "user_id": params["uid"], "kind": "lab", "status": "ready",
                              "title": params["title"], "symbols": [params["symbol"]],
                              "content": json.loads(params["content"]), "credits_used": params["credits"],
                              "created_at": NOW, "expires_at": NOW + timedelta(days=30)})
            return _Result(scalar=new_id)
        raise AssertionError(sql)

    def rollback(self):
        pass


class _Result:
    def __init__(self, rows=None, rowcount=0, scalar=None):
        self._rows, self.rowcount, self._scalar = rows or [], rowcount, scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def scalar(self):
        return self._scalar


def _item(id_, user_id, created_days_ago, expires_in_days, title="t"):
    return {"id": id_, "user_id": user_id, "kind": "lab", "status": "ready", "title": title, "symbols": ["005930"],
            "content": {"stock_code": "005930"}, "credits_used": 3,
            "created_at": NOW - timedelta(days=created_days_ago), "expires_at": NOW + timedelta(days=expires_in_days)}


def test_lab_title_matches_frontend_shape():
    assert items.lab_title("삼성전자", DIRS) == "삼성전자 · 국제유가 상승·미국 10년물 국채금리 하락 실험"


def test_days_left_rounds_up():
    assert items.days_left(NOW + timedelta(days=24, hours=1), NOW) == 25
    assert items.days_left(NOW - timedelta(hours=1), NOW) == 0


def test_list_only_mine_not_expired_newest_first():
    db = FakeDb([_item(1, 7, 3, 27), _item(2, 7, 1, 29), _item(3, 8, 0, 30), _item(4, 7, 31, -1)])
    out = items.list_items(db, 7, NOW)
    assert [r["id"] for r in out] == ["2", "1"]
    assert out[0]["days_left"] == 29 and out[0]["symbols"] == ["005930"]


def client(monkeypatch, db: FakeDb, answer=GOOD, user=7):
    @contextmanager
    def session():
        yield db

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": user}
    app.dependency_overrides[get_read_db] = lambda: db
    monkeypatch.setattr(routes, "_stock", lambda _db, code: STOCK if code == "005930" else None)
    monkeypatch.setattr(routes, "_macro", lambda _db: ([], ""))
    monkeypatch.setattr(routes, "get_session", session)
    monkeypatch.setattr(routes, "openai_call", fake(answer))
    monkeypatch.setattr(routes.ledger, "cost", lambda _reason: 3)
    monkeypatch.setattr(routes.ledger, "refresh", lambda _db, _user: None)
    monkeypatch.setattr(routes.ledger, "balance", lambda _db, _user: 30)
    monkeypatch.setattr(routes.ledger, "spend", lambda _db, user, amount, reason: amount)
    return TestClient(app)


def test_delete_moves_only_mine_to_trash(monkeypatch):
    db = FakeDb([_item(1, 7, 0, 30), _item(2, 8, 0, 30)])
    api = client(monkeypatch, db)
    assert api.delete("/api/v1/studio/items/2").status_code == 404      # 남의 것
    assert api.delete("/api/v1/studio/items/1").status_code == 204
    assert [r["id"] for r in db.rows] == [1, 2]                         # 줄은 남고 (휴지통)
    assert db.rows[0]["deleted_at"] == NOW and db.rows[1].get("deleted_at") is None
    assert api.get("/api/v1/studio/items").json() == []                 # 목록에서는 빠짐
    assert api.delete("/api/v1/studio/items/1").status_code == 404      # 이미 휴지통


def test_lab_saves_item_and_lists_it(monkeypatch):
    db = FakeDb()
    api = client(monkeypatch, db)
    res = api.post("/api/v1/studio/lab", json={"stock_code": "005930", "dirs": DIRS})
    assert res.status_code == 200 and res.json()["item_id"] == "1"
    row = db.rows[0]
    assert row["title"] == "삼성전자 · 국제유가 상승·미국 10년물 국채금리 하락 실험" and row["credits_used"] == 3
    assert row["content"]["dirs"] == DIRS and row["content"]["groups"] == res.json()["groups"]
    listed = api.get("/api/v1/studio/items").json()
    assert [r["id"] for r in listed] == ["1"] and listed[0]["content"]["name"] == "삼성전자"


def test_lab_fallback_is_not_saved(monkeypatch):
    db = FakeDb()
    res = client(monkeypatch, db, answer=TimeoutError("timeout")).post(
        "/api/v1/studio/lab", json={"stock_code": "005930", "dirs": DIRS})
    assert res.status_code == 200 and res.json()["source"] == "rules" and res.json()["item_id"] is None
    assert db.rows == []


def test_lab_result_returned_even_if_save_fails(monkeypatch):
    db = FakeDb(fail_insert=True)
    res = client(monkeypatch, db).post("/api/v1/studio/lab", json={"stock_code": "005930", "dirs": DIRS})
    assert res.status_code == 200 and res.json()["item_id"] is None and res.json()["groups"]
