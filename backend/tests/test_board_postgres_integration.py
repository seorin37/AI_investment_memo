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


def test_postgres_board_order_new_front_after_pinned_and_reorder(isolated_db):
    """보드 순서 (0019 memos.position): 새 카드는 맨 앞이되 고정 카드들 뒤, 테이프를 붙이면 맨 앞, 전체 순서 저장."""
    engine, (user_a, user_b) = isolated_db
    current = {"id": str(user_a)}
    client = _client(engine, current)
    board_url = f"/api/v1/stocks/{SYMBOLS[0]}/board"

    def memo(title: str, pinned: bool = False) -> int:
        response = client.post(f"/api/v1/stocks/{SYMBOLS[0]}/memos", json={
            "title": title, "body": "b", "tags": [], "color": "yellow", "ai_linked": False, "pinned": pinned,
        })
        assert response.status_code == 201
        return int(response.json()["id"])

    def titles() -> list[str]:
        board = client.get(board_url).json()
        assert [item["position"] for item in board] == list(range(len(board)))
        return [item["title"] for item in board]

    other = client.post(f"/api/v1/stocks/{SYMBOLS[1]}/memos", json={
        "title": "다른 종목", "body": "b", "tags": [], "color": "yellow", "ai_linked": False,
    }).json()["id"]
    a, b, c = memo("A"), memo("B"), memo("C")
    assert titles() == ["C", "B", "A"]                          # 새 카드는 맨 앞
    p = memo("P", pinned=True)
    assert titles() == ["P", "C", "B", "A"]                     # 고정 카드는 맨 앞
    d = memo("D")
    assert titles() == ["P", "D", "C", "B", "A"]                # 새 카드는 고정 카드들 뒤
    checklist = client.post(f"/api/v1/stocks/{SYMBOLS[0]}/checklists", json={"title": "체크", "items": []})
    assert checklist.json()["position"] == 1
    assert titles() == ["P", "체크", "D", "C", "B", "A"]

    saved = client.put(f"/api/v1/stocks/{SYMBOLS[0]}/board-order", json={"ids": [a, p]})
    assert saved.status_code == 200
    assert [item["title"] for item in saved.json()] == ["A", "P", "체크", "D", "C", "B"]   # 빠진 카드는 지금 순서대로 뒤에
    assert client.patch(f"/api/v1/board-items/{a}", json={"position": 99}).json()["position"] == 5
    assert titles() == ["P", "체크", "D", "C", "B", "A"]

    client.patch(f"/api/v1/board-items/{b}", json={"pinned": True})
    assert titles() == ["B", "P", "체크", "D", "C", "A"]        # 테이프 붙이면 맨 앞
    client.patch(f"/api/v1/board-items/{b}", json={"pinned": False})
    assert titles() == ["P", "B", "체크", "D", "C", "A"]        # 떼면 고정 카드들 바로 뒤

    assert client.delete(f"/api/v1/board-items/{d}").status_code == 204
    assert titles() == ["P", "B", "체크", "C", "A"]
    assert client.put(f"/api/v1/stocks/{SYMBOLS[0]}/board-order", json={"ids": [d]}).status_code == 422   # 지운 카드
    assert client.put(f"/api/v1/stocks/{SYMBOLS[0]}/board-order", json={"ids": [int(other)]}).status_code == 422  # 다른 종목
    assert client.put(f"/api/v1/stocks/{SYMBOLS[0]}/board-order", json={"ids": [c, c]}).status_code == 422
    with engine.connect() as connection:
        live = connection.execute(text(
            "SELECT position FROM memos WHERE user_id = :u AND symbol = :s AND deleted_at IS NULL ORDER BY position"
        ), {"u": user_a, "s": SYMBOLS[0]}).scalars().all()
        assert live == [0, 1, 2, 3, 4]                          # 저장값도 0부터 빈틈없이 (지운 카드 뒤 다시 쓴 뒤)
    assert client.get(f"/api/v1/stocks/{SYMBOLS[1]}/board").json()[0]["position"] == 0   # 다른 보드는 그대로

    current["id"] = str(user_b)
    assert client.put(f"/api/v1/stocks/{SYMBOLS[0]}/board-order", json={"ids": [a]}).status_code == 404


def test_postgres_memo_questions_saved_as_ask_items_once(isolated_db):
    """메모 분석이 찾은 질문(0019): type=ask 항목으로 저장, 답해서 done이 된 같은 질문은 다시 저장해도 새로 만들지 않는다."""
    from app.board.tracking import TrackingRepository
    engine, (user_a, _user_b) = isolated_db
    with Session(engine) as session:
        memo_id = session.execute(text("INSERT INTO memos (user_id, symbol, kind, title, content) VALUES (:u, :s, 'note', '실적', '얼마야?') RETURNING id"),
                                  {"u": user_a, "s": SYMBOLS[0]}).scalar_one()
        repo = TrackingRepository(session)
        first = repo.sync(memo_id, [{"type": "topic", "description": "실적 소식", "keywords": []}], [],
                          [{"question": "3분기 영업이익률이 얼마인지", "kind": "check"}])
        assert sorted(e["type"] for e in first["created"]) == ["ask", "topic"]
        ask_id = next(e["id"] for e in first["created"] if e["type"] == "ask")
        session.execute(text("UPDATE tracking_items SET status = 'done' WHERE id = :i"), {"i": ask_id})   # 매일 실행이 답함
        again = repo.sync(memo_id, [{"type": "topic", "description": "실적 소식", "keywords": []}], [],
                          [{"question": "3분기  영업이익률이 얼마인지", "kind": "check"}])
        assert again["created"] == []                                   # 이미 답한 질문은 다시 만들지 않는다
        new_q = repo.sync(memo_id, [], [], [{"question": "배당은 얼마인지", "kind": "check"}])
        assert [e["type"] for e in new_q["created"]] == ["ask"]
        session.rollback()
