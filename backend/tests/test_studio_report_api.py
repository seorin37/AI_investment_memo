"""주간보고서 API POST /studio/reports (2026-11-23). DB·LLM 없이 가짜 세션으로 흐름만 확인한다."""
from __future__ import annotations

import json
from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.routes import get_current_user
from app.db import get_read_db
from app.studio_report import routes


class _Res:
    def __init__(self, rows=None, scalar=None):
        self._rows, self._scalar = rows or [], scalar

    def all(self):
        return self._rows

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._scalar


class FakeDb:
    def __init__(self, mine=("000660", "005930"), same=None):
        self.mine, self.same, self.calls = mine, same, []

    def execute(self, stmt, params=None):
        sql = str(stmt).lstrip()
        self.calls.append((sql.split()[0], params))
        if "FROM user_stocks" in sql:
            return _Res([(c,) for c in self.mine])
        if sql.startswith("SELECT id, status FROM studio_items"):
            return _Res([self.same] if self.same else [])
        if sql.startswith("INSERT"):
            return _Res(scalar=42)
        return _Res()

    def rollback(self):
        pass


def client(monkeypatch, db: FakeDb, balance=30, built=None, fail=False):
    spent, generated = [], []

    @contextmanager
    def session():
        yield db

    def fake_build(_db, user_id, codes, today=None, market=False, llm=None):
        if fail:
            raise RuntimeError("boom")
        return built or {"stocks": [{"stock_code": c} for c in codes], "sources": [{"no": 1, "ref": "news:1", "text": "x"}],
                         "market": [{"name": "코스피"}] if market else []}

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": 2}
    app.dependency_overrides[get_read_db] = lambda: db
    monkeypatch.setattr(routes, "get_session", session)
    monkeypatch.setattr(routes, "get_read_session", session)
    monkeypatch.setattr(routes, "build_report", fake_build)
    monkeypatch.setattr(routes, "_llm", lambda: None)
    monkeypatch.setattr(routes.ledger, "cost", lambda _r: 5)
    monkeypatch.setattr(routes.ledger, "refresh", lambda _db, _u: None)
    monkeypatch.setattr(routes.ledger, "balance", lambda _db, _u: balance)
    monkeypatch.setattr(routes.ledger, "spend", lambda _db, u, a, r, k=None, i=None: spent.append((u, a, r, k, i)) or a)
    orig = routes.generate
    monkeypatch.setattr(routes, "generate", lambda *a, **k: generated.append(a) or orig(*a, **k))
    return TestClient(app), spent, generated


def test_creates_and_generates_in_background(monkeypatch):
    db = FakeDb()
    api, spent, generated = client(monkeypatch, db)
    res = api.post("/api/v1/studio/reports", json={"codes": ["005930", "000660"], "market": True})
    assert res.status_code == 202 and res.json() == {"item_id": "42", "status": "generating", "reused": False}
    assert generated == [(42, 2, ["000660", "005930"], True)]               # 정렬된 종목
    assert spent == [(2, 5, "report", "studio_item", 42)]                     # 성공했을 때 크레딧 5
    ready = [p for op, p in db.calls if op == "UPDATE" and "content" in p]
    content = json.loads(ready[0]["content"])
    assert content["market_on"] is True and content["market"] == [{"name": "코스피"}]   # 지수 목록과 켜짐 표시가 겹치지 않는다
    assert json.loads(ready[0]["sources"]) == [{"no": 1, "ref": "news:1"}]


def test_reuses_same_week_same_codes(monkeypatch):
    api, spent, generated = client(monkeypatch, FakeDb(same={"id": 7, "status": "ready"}))
    res = api.post("/api/v1/studio/reports", json={"codes": ["000660"]})
    assert res.json() == {"item_id": "7", "status": "ready", "reused": True}
    assert generated == [] and spent == []


def test_rejects_other_stock_and_low_credit(monkeypatch):
    api, spent, _ = client(monkeypatch, FakeDb())
    assert api.post("/api/v1/studio/reports", json={"codes": ["035420"]}).status_code == 422
    api, spent, generated = client(monkeypatch, FakeDb(), balance=4)
    assert api.post("/api/v1/studio/reports", json={"codes": ["000660"]}).status_code == 402
    assert spent == [] and generated == []


def test_failure_marks_failed_without_credit(monkeypatch):
    db = FakeDb()
    api, spent, _ = client(monkeypatch, db, fail=True)
    assert api.post("/api/v1/studio/reports", json={"codes": ["000660"]}).status_code == 202
    assert spent == []
    assert [p for op, p in db.calls if op == "UPDATE"] == [{"id": 42, "error": "RuntimeError"}]


def test_trashed_report_is_not_reused():
    """휴지통에 넣은 보고서(deleted_at, 0025)를 '같은 주 같은 종목'으로 다시 쓰면 새로 만들어도 목록에 안 보인다 → 다시 쓰지 않는다."""
    from app.studio_report import routes as report_routes

    assert "deleted_at IS NULL" in report_routes.SAME_SQL
