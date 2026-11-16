"""Isolated PostgreSQL integration tests for memo-board CRUD."""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.board.routes import router
from app.db import get_db, get_read_db


TEST_URL = os.getenv("BOARD_API_TEST_DATABASE_URL", "")
TEST_ALLOWED = os.getenv("BOARD_API_TEST_ALLOW") == "1"
SYMBOLS = ("B00001", "B00002")
EMAILS = ("board-api-a@example.test", "board-api-b@example.test")


def _engine():
    if not TEST_URL or not TEST_ALLOWED:
        pytest.skip("explicit isolated PostgreSQL test database was not provided")
    parsed = make_url(TEST_URL)
    if not (parsed.database or "").endswith("_test"):
        pytest.fail("refusing to use a database whose name does not end with _test")
    return create_engine(TEST_URL, pool_pre_ping=True)


@pytest.fixture()
def isolated_db():
    engine = _engine()
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM memos WHERE symbol = ANY(:symbols)"), {"symbols": list(SYMBOLS)})
        connection.execute(text("DELETE FROM tags WHERE user_id IN (SELECT id FROM users WHERE email = ANY(:emails))"), {"emails": list(EMAILS)})
        connection.execute(text("DELETE FROM user_stocks WHERE symbol = ANY(:symbols)"), {"symbols": list(SYMBOLS)})
        connection.execute(text("DELETE FROM users WHERE email = ANY(:emails)"), {"emails": list(EMAILS)})
        connection.execute(text("DELETE FROM stocks WHERE symbol = ANY(:symbols)"), {"symbols": list(SYMBOLS)})
        connection.execute(text("INSERT INTO stocks (symbol, name, market) VALUES (:a, '보드전자', 'KOSPI'), (:b, '보드금융', 'KOSPI')"), {"a": SYMBOLS[0], "b": SYMBOLS[1]})
        user_ids = connection.execute(text("INSERT INTO users (email, display_name) VALUES (:a, '사용자 A'), (:b, '사용자 B') RETURNING id"), {"a": EMAILS[0], "b": EMAILS[1]}).scalars().all()
        connection.execute(text("INSERT INTO user_stocks (user_id, symbol, status) VALUES (:user_a, :symbol_a, 'watching'), (:user_a, :symbol_b, 'holding')"), {"user_a": user_ids[0], "symbol_a": SYMBOLS[0], "symbol_b": SYMBOLS[1]})
    yield engine, tuple(user_ids)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM memos WHERE symbol = ANY(:symbols)"), {"symbols": list(SYMBOLS)})
        connection.execute(text("DELETE FROM tags WHERE user_id IN (SELECT id FROM users WHERE email = ANY(:emails))"), {"emails": list(EMAILS)})
        connection.execute(text("DELETE FROM user_stocks WHERE symbol = ANY(:symbols)"), {"symbols": list(SYMBOLS)})
        connection.execute(text("DELETE FROM users WHERE email = ANY(:emails)"), {"emails": list(EMAILS)})
        connection.execute(text("DELETE FROM stocks WHERE symbol = ANY(:symbols)"), {"symbols": list(SYMBOLS)})
    engine.dispose()


def _client(engine, current_user: dict[str, str]) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def read_db():
        with Session(engine) as session:
            yield session

    def write_db():
        with Session(engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_read_db] = read_db
    app.dependency_overrides[get_db] = write_db
    app.dependency_overrides[get_current_user] = lambda: current_user
    return TestClient(app)


def test_postgres_board_crud_revision_children_and_ownership(isolated_db):
    engine, (user_a, user_b) = isolated_db
    current = {"id": str(user_a)}
    client = _client(engine, current)

    memo = client.post(f"/api/v1/stocks/{SYMBOLS[0]}/memos", json={
        "title": "초기 제목", "body": "초기 본문", "tags": ["실적", "장기"],
        "color": "green", "ai_linked": True, "pinned": True,
    })
    assert memo.status_code == 201
    memo_id = int(memo.json()["id"])
    checklist = client.post(f"/api/v1/stocks/{SYMBOLS[0]}/checklists", json={
        "title": "체크", "items": [{"text": "공시 확인", "done": False}],
    })
    reference = client.post(f"/api/v1/stocks/{SYMBOLS[1]}/references", json={
        "title": "참고", "links": [{"title": "IR", "url": "https://example.com/ir", "ref_type": "ir", "source": "link"}],
    })
    assert checklist.status_code == reference.status_code == 201

    board = client.get(f"/api/v1/stocks/{SYMBOLS[0]}/board").json()
    assert {item["kind"] for item in board} == {"memo", "checklist"}
    assert client.get(f"/api/v1/stocks/{SYMBOLS[1]}/board").json()[0]["kind"] == "reference"

    changed = client.patch(f"/api/v1/board-items/{memo_id}", json={
        "title": "수정 제목", "body": "수정 본문", "tags": ["업데이트"],
    })
    assert changed.status_code == 200
    assert changed.json()["tags"] == ["업데이트"]

    checklist_id = int(checklist.json()["id"])
    item_id = int(checklist.json()["items"][0]["id"])
    item_changed = client.patch(f"/api/v1/checklists/{checklist_id}/items/{item_id}", json={"done": True})
    assert item_changed.json()["items"][0]["done"] is True

    reference_id = int(reference.json()["id"])
    ref_changed = client.patch(f"/api/v1/board-items/{reference_id}", json={
        "links": [{"title": "공시", "url": "https://example.com/d", "ref_type": "disclosure", "source": "link"}],
    })
    assert ref_changed.json()["links"][0]["ref_type"] == "disclosure"

    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM memo_revisions WHERE memo_id = :id"), {"id": memo_id}).scalar_one() == 2
        assert connection.execute(text("SELECT content FROM memos WHERE id = :id"), {"id": memo_id}).scalar_one() == "수정 본문"
        assert connection.execute(text("SELECT count(*) FROM memo_tags WHERE memo_id = :id"), {"id": memo_id}).scalar_one() == 1

    current["id"] = str(user_b)
    assert client.get(f"/api/v1/board-items/{memo_id}").status_code == 404
    assert client.patch(f"/api/v1/board-items/{memo_id}", json={"title": "침범"}).status_code == 404
    assert client.delete(f"/api/v1/board-items/{memo_id}").status_code == 404
    assert client.get(f"/api/v1/stocks/{SYMBOLS[0]}/board").status_code == 404

    current["id"] = str(user_a)
    assert client.delete(f"/api/v1/board-items/{memo_id}").status_code == 204
    assert client.get(f"/api/v1/board-items/{memo_id}").status_code == 404
    with engine.connect() as connection:
        assert connection.execute(text("SELECT deleted_at IS NOT NULL FROM memos WHERE id = :id"), {"id": memo_id}).scalar_one()


def test_postgres_transaction_rollback_and_schema_constraints(isolated_db):
    engine, (user_a, _user_b) = isolated_db
    with Session(engine) as session:
        row_id = session.execute(text("INSERT INTO memos (user_id, symbol, kind, title, content) VALUES (:user_id, :symbol, 'note', 'rollback', 'body') RETURNING id"), {"user_id": user_a, "symbol": SYMBOLS[0]}).scalar_one()
        session.rollback()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM memos WHERE id = :id"), {"id": row_id}).scalar_one() == 0
        constraints = set(connection.execute(text("SELECT constraint_type FROM information_schema.table_constraints WHERE table_schema = 'public' AND table_name IN ('memos', 'checklist_items', 'memo_links')" )).scalars())
        assert {"PRIMARY KEY", "FOREIGN KEY"}.issubset(constraints)
