"""Isolated PostgreSQL integration tests for the stock API.

The tests are skipped unless an explicitly marked test database is supplied.
They must never fall back to the project's normal DATABASE_URL.
"""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.db import get_db, get_read_db
from app.stocks.repository import StockRepository
from app.stocks.routes import router


TEST_URL = os.getenv("STOCK_API_TEST_DATABASE_URL", "")
TEST_ALLOWED = os.getenv("STOCK_API_TEST_ALLOW") == "1"
SYMBOL = "T00001"
SECOND_SYMBOL = "T00002"
USER_EMAILS = ("stock-api-a@example.test", "stock-api-b@example.test")


def _test_engine():
    if not TEST_URL or not TEST_ALLOWED:
        pytest.skip("explicit isolated PostgreSQL test database was not provided")
    parsed = make_url(TEST_URL)
    if not (parsed.database or "").endswith("_test"):
        pytest.fail("refusing to use a database whose name does not end with _test")
    return create_engine(TEST_URL, pool_pre_ping=True)


@pytest.fixture()
def isolated_db():
    engine = _test_engine()
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM user_stocks WHERE symbol IN (:one, :two)"),
            {"one": SYMBOL, "two": SECOND_SYMBOL},
        )
        connection.execute(
            text("DELETE FROM users WHERE email IN (:a, :b)"),
            {"a": USER_EMAILS[0], "b": USER_EMAILS[1]},
        )
        connection.execute(
            text("DELETE FROM stocks WHERE symbol IN (:one, :two)"),
            {"one": SYMBOL, "two": SECOND_SYMBOL},
        )
        connection.execute(
            text(
                """
                INSERT INTO stocks (symbol, name, market)
                VALUES (:one, '테스트전자', 'KOSPI'),
                       (:two, '테스트금융', 'KOSPI')
                """
            ),
            {"one": SYMBOL, "two": SECOND_SYMBOL},
        )
        user_ids = connection.execute(
            text(
                """
                INSERT INTO users (email, display_name)
                VALUES (:a, '사용자 A'), (:b, '사용자 B')
                RETURNING id
                """
            ),
            {"a": USER_EMAILS[0], "b": USER_EMAILS[1]},
        ).scalars().all()

    yield engine, tuple(user_ids)

    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM user_stocks WHERE symbol IN (:one, :two)"),
            {"one": SYMBOL, "two": SECOND_SYMBOL},
        )
        connection.execute(
            text("DELETE FROM users WHERE email IN (:a, :b)"),
            {"a": USER_EMAILS[0], "b": USER_EMAILS[1]},
        )
        connection.execute(
            text("DELETE FROM stocks WHERE symbol IN (:one, :two)"),
            {"one": SYMBOL, "two": SECOND_SYMBOL},
        )
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


def test_postgres_stock_crud_upsert_soft_delete_and_user_isolation(isolated_db):
    engine, (user_a, user_b) = isolated_db
    current = {"id": str(user_a)}
    client = _client(engine, current)

    search = client.get("/api/v1/stocks/search", params={"q": "테스트전자"})
    assert search.status_code == 200
    assert search.json()[0]["code"] == SYMBOL

    created = client.post(
        "/api/v1/stocks", json={"code": SYMBOL, "status": "watching"}
    )
    assert created.status_code == 200
    assert created.json()["status"] == "watching"

    duplicate = client.post(
        "/api/v1/stocks", json={"code": SYMBOL, "status": "holding"}
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "holding"
    with engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT count(*) FROM user_stocks "
                "WHERE user_id = :user_id AND symbol = :symbol"
            ),
            {"user_id": user_a, "symbol": SYMBOL},
        ).scalar_one() == 1

    changed = client.patch(
        f"/api/v1/stocks/{SYMBOL}", json={"status": "watching"}
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "watching"

    assert client.delete(f"/api/v1/stocks/{SYMBOL}").status_code == 204
    assert client.get("/api/v1/stocks").json() == []
    with engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT deleted_at IS NOT NULL FROM user_stocks "
                "WHERE user_id = :user_id AND symbol = :symbol"
            ),
            {"user_id": user_a, "symbol": SYMBOL},
        ).scalar_one()

    restored = client.post(
        "/api/v1/stocks", json={"code": SYMBOL, "status": "holding"}
    )
    assert restored.status_code == 200
    with engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT deleted_at IS NULL FROM user_stocks "
                "WHERE user_id = :user_id AND symbol = :symbol"
            ),
            {"user_id": user_a, "symbol": SYMBOL},
        ).scalar_one()

    current["id"] = str(user_b)
    assert client.get("/api/v1/stocks").json() == []
    assert client.patch(
        f"/api/v1/stocks/{SYMBOL}", json={"status": "watching"}
    ).status_code == 404
    assert client.delete(f"/api/v1/stocks/{SYMBOL}").status_code == 404
    assert client.post(
        "/api/v1/stocks", json={"code": SYMBOL, "status": "watching"}
    ).status_code == 200

    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM user_stocks WHERE symbol = :symbol"),
            {"symbol": SYMBOL},
        ).scalar_one() == 2


def test_postgres_transaction_rollback_and_foreign_keys(isolated_db):
    engine, (user_a, _user_b) = isolated_db
    with Session(engine) as session:
        repository = StockRepository(session)
        repository.upsert_user_stock(user_a, SECOND_SYMBOL, "watching")
        session.rollback()

    with engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT count(*) FROM user_stocks "
                "WHERE user_id = :user_id AND symbol = :symbol"
            ),
            {"user_id": user_a, "symbol": SECOND_SYMBOL},
        ).scalar_one() == 0

        constraints = set(
            connection.execute(
                text(
                    """
                    SELECT constraint_type
                    FROM information_schema.table_constraints
                    WHERE table_schema = 'public' AND table_name = 'user_stocks'
                    """
                )
            ).scalars()
        )
        assert {"PRIMARY KEY", "FOREIGN KEY"}.issubset(constraints)


def test_postgres_sidebar_stock_order(isolated_db):
    """사이드바 내 종목 순서 (0021 user_stocks.position): 새 종목은 맨 뒤, 전체 순서 저장, 지웠다 다시 추가하면 맨 뒤."""
    engine, (user_a, user_b) = isolated_db
    current = {"id": str(user_a)}
    client = _client(engine, current)
    with engine.connect() as c:
        if not c.execute(text("SELECT count(*) FROM information_schema.columns WHERE table_name = 'user_stocks' "
                              "AND column_name = 'position'")).scalar():
            pytest.skip("0021 전 DB")
    first = client.post("/api/v1/stocks", json={"code": SYMBOL, "status": "watching"}).json()
    second = client.post("/api/v1/stocks", json={"code": SECOND_SYMBOL, "status": "holding"}).json()
    assert (first["position"], second["position"]) == (0, 1)                  # 새 종목은 맨 뒤
    codes = lambda: [s["code"] for s in client.get("/api/v1/stocks").json()]
    assert codes() == [SYMBOL, SECOND_SYMBOL]

    saved = client.put("/api/v1/stocks/order", json={"codes": [SECOND_SYMBOL]})
    assert saved.status_code == 200
    assert [(s["code"], s["position"]) for s in saved.json()] == [(SECOND_SYMBOL, 0), (SYMBOL, 1)]   # 빠진 종목은 뒤에
    assert client.patch(f"/api/v1/stocks/{SYMBOL}", json={"status": "holding"}).json()["position"] == 1  # 상태만 바꾸면 자리 그대로

    assert client.put("/api/v1/stocks/order", json={"codes": [SYMBOL, SYMBOL]}).status_code == 422     # 중복
    assert client.put("/api/v1/stocks/order", json={"codes": ["005930"]}).status_code == 422           # 내 종목 아님

    assert client.delete(f"/api/v1/stocks/{SECOND_SYMBOL}").status_code == 204
    assert client.put("/api/v1/stocks/order", json={"codes": [SECOND_SYMBOL]}).status_code == 422      # 지운 종목
    again = client.post("/api/v1/stocks", json={"code": SECOND_SYMBOL, "status": "watching"}).json()
    assert again["position"] == 1 and codes() == [SYMBOL, SECOND_SYMBOL]      # 다시 추가하면 맨 뒤

    current["id"] = str(user_b)
    assert client.get("/api/v1/stocks").json() == []                         # 다른 사용자와 섞이지 않음
