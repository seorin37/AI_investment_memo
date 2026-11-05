"""Stock API contract tests without central DB or external services."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth.routes import get_current_user
from app.stocks.routes import get_command_service, get_query_service, router
from app.stocks.service import (
    StockNotFoundError,
    UnsupportedStockTagsError,
    UserStockNotFoundError,
)


class FakeStockService:
    masters = {
        "005930": {"code": "005930", "name": "삼성전자", "market": "KOSPI"},
        "000080": {"code": "000080", "name": "하이트진로", "market": "KOSPI"},
        "00104K": {"code": "00104K", "name": "CJ4우(전환)", "market": "KOSPI"},
    }

    def __init__(self) -> None:
        self.rows: dict[tuple[int, str], dict] = {}

    def search(self, query: str):
        key = query.strip().lower()
        return [
            value
            for value in self.masters.values()
            if key in value["code"].lower() or key in value["name"].lower()
        ][:8]

    def get_master(self, code: str):
        if code not in self.masters:
            raise StockNotFoundError(code)
        return self.masters[code]

    def list_mine(self, user_id: int):
        return [row for (owner, _), row in self.rows.items() if owner == user_id]

    def add(self, user_id: int, code: str, status: str):
        master = self.get_master(code)
        key = (user_id, code)
        if key in self.rows:
            self.rows[key]["status"] = status
            return self.rows[key]
        self.rows[key] = {
            **master,
            "status": status,
            "tags": [],
            "unread_updates": 0,
            "added_at": datetime(2026, 11, 5, tzinfo=timezone.utc),
        }
        return self.rows[key]

    def update(self, user_id: int, code: str, *, status, tags):
        if tags not in (None, []):
            raise UnsupportedStockTagsError("현재 DB 스키마에는 종목 태그 저장 구조가 없습니다.")
        key = (user_id, code)
        if key not in self.rows:
            raise UserStockNotFoundError(code)
        if status is not None:
            self.rows[key]["status"] = status
        return self.rows[key]

    def remove(self, user_id: int, code: str):
        key = (user_id, code)
        if key not in self.rows:
            raise UserStockNotFoundError(code)
        del self.rows[key]


class StockApiTest(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.service = FakeStockService()
        self.current_user = {"id": "1"}
        self.app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.app.dependency_overrides[get_query_service] = lambda: self.service
        self.app.dependency_overrides[get_command_service] = lambda: self.service
        self.client = TestClient(self.app)

    def test_search_and_master_detail(self):
        search = self.client.get("/api/v1/stocks/search", params={"q": "삼성"})
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json(), [FakeStockService.masters["005930"]])

        detail = self.client.get("/api/v1/stocks/00104K")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["code"], "00104K")

    def test_add_watching_and_holding(self):
        watching = self.client.post(
            "/api/v1/stocks", json={"code": "005930", "status": "watching"}
        )
        holding = self.client.post(
            "/api/v1/stocks", json={"code": "000080", "status": "holding"}
        )
        self.assertEqual(watching.status_code, 200)
        self.assertEqual(watching.json()["status"], "watching")
        self.assertEqual(holding.json()["status"], "holding")
        self.assertEqual(len(self.client.get("/api/v1/stocks").json()), 2)

    def test_duplicate_add_changes_status_without_duplicate(self):
        self.client.post(
            "/api/v1/stocks", json={"code": "005930", "status": "watching"}
        )
        changed = self.client.post(
            "/api/v1/stocks", json={"code": "005930", "status": "holding"}
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json()["status"], "holding")
        self.assertEqual(len(self.client.get("/api/v1/stocks").json()), 1)

    def test_patch_status_and_delete(self):
        self.client.post(
            "/api/v1/stocks", json={"code": "005930", "status": "watching"}
        )
        changed = self.client.patch(
            "/api/v1/stocks/005930", json={"status": "holding"}
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json()["status"], "holding")
        deleted = self.client.delete("/api/v1/stocks/005930")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get("/api/v1/stocks").json(), [])

    def test_missing_stock_and_invalid_symbol(self):
        missing = self.client.post(
            "/api/v1/stocks", json={"code": "999999", "status": "watching"}
        )
        invalid = self.client.post(
            "/api/v1/stocks", json={"code": "abc", "status": "watching"}
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(invalid.status_code, 422)

    def test_nonempty_tags_rejected_instead_of_silently_lost(self):
        self.client.post(
            "/api/v1/stocks", json={"code": "005930", "status": "watching"}
        )
        response = self.client.patch(
            "/api/v1/stocks/005930", json={"tags": ["장기"]}
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("태그 저장 구조", response.json()["detail"])

    def test_user_data_isolation_and_cross_user_mutations_fail(self):
        self.client.post(
            "/api/v1/stocks", json={"code": "005930", "status": "watching"}
        )
        self.current_user["id"] = "2"
        self.assertEqual(self.client.get("/api/v1/stocks").json(), [])
        self.assertEqual(
            self.client.patch(
                "/api/v1/stocks/005930", json={"status": "holding"}
            ).status_code,
            404,
        )
        self.assertEqual(self.client.delete("/api/v1/stocks/005930").status_code, 404)
        self.current_user["id"] = "1"
        self.assertEqual(self.client.get("/api/v1/stocks").json()[0]["status"], "watching")

    def test_unauthenticated_request_is_rejected(self):
        def reject_unauthenticated():
            raise HTTPException(status_code=401, detail="Not authenticated")

        self.app.dependency_overrides[get_current_user] = reject_unauthenticated
        response = self.client.get("/api/v1/stocks")
        self.assertEqual(response.status_code, 401)


class StockRepositoryOwnershipGuardTest(unittest.TestCase):
    def test_mutating_sql_filters_by_authenticated_user(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "stocks"
            / "repository.py"
        ).read_text(encoding="utf-8")
        self.assertIn("ON CONFLICT (user_id, symbol)", source)
        self.assertGreaterEqual(source.count("WHERE user_id = :user_id"), 2)
        self.assertNotIn("DELETE FROM user_stocks", source)


if __name__ == "__main__":
    unittest.main()
