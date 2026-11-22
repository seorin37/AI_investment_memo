"""홈 배치 · 설정 · 내 프로필 API 테스트 (중앙 DB 없이 메모리 저장소 사용)."""

from __future__ import annotations

import unittest
from datetime import datetime, time, timezone
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.account.defaults import DEFAULT_SETTINGS
from app.account.repository import AccountRepository
from app.account.routes import (
    get_account_command_service,
    get_account_query_service,
    router,
)
from app.account.service import AccountService
from app.auth.routes import get_auth_service, get_current_user


class FakeAccountRepo:
    def __init__(self) -> None:
        self.user_settings: dict[int, dict] = {}
        self.mcp_settings: dict[int, dict] = {}
        self.mcp_apps: dict[int, list[dict]] = {}
        self.profiles: dict[int, dict] = {}

    def get_user_settings(self, user_id):
        return self.user_settings.get(user_id)

    def get_mcp_settings(self, user_id):
        return self.mcp_settings.get(user_id)

    def list_mcp_apps(self, user_id):
        return self.mcp_apps.get(user_id, [])

    def upsert_user_settings(self, user_id, columns):
        self.user_settings.setdefault(user_id, {}).update(columns)

    def upsert_mcp_settings(self, user_id, columns):
        self.mcp_settings.setdefault(user_id, {}).update(columns)

    def get_home_layout(self, user_id):
        return self.user_settings.get(user_id, {}).get("home_layout")

    def save_home_layout(self, user_id, layout):
        self.user_settings.setdefault(user_id, {})["home_layout"] = layout

    def update_profile(self, user_id, *, display_name, bio):
        row = self.profiles[user_id]
        if display_name is not None:
            row["display_name"] = display_name
        if bio is not None:
            row["bio"] = bio


class FakeAuthRepo:
    def __init__(self, profiles: dict[int, dict]) -> None:
        self.profiles = profiles

    def get_user(self, user_id):
        row = self.profiles.get(user_id)
        if not row:
            return None
        return {
            **row,
            "providers": [
                {"provider": "kakao", "email": row["email"], "connected": True, "current": False}
            ],
        }


class AccountApiTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeAccountRepo()
        self.repo.profiles[7] = {
            "id": 7,
            "email": "u7@example.com",
            "display_name": "서린",
            "bio": None,
            "avatar_url": None,
            "plan": "free",
            "deleted_at": None,
        }
        service = AccountService(self.repo, FakeAuthRepo(self.repo.profiles))
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"id": "7"}
        app.dependency_overrides[get_account_query_service] = lambda: service
        app.dependency_overrides[get_account_command_service] = lambda: service
        self.client = TestClient(app)

    # ─── 홈 배치
    def test_home_layout_defaults_to_mock_unset_layout(self):
        res = self.client.get("/api/v1/home/layout")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"mode": "unset", "widgets": []})

    def test_home_layout_put_then_get_round_trips(self):
        layout = {
            "mode": "custom",
            "widgets": [
                {"id": "w1", "type": "market", "span": 4},
                {"id": "w2", "type": "news", "span": 2},
            ],
        }
        put = self.client.put("/api/v1/home/layout", json=layout)
        self.assertEqual(put.status_code, 200)
        self.assertEqual(put.json(), layout)
        self.assertEqual(self.client.get("/api/v1/home/layout").json(), layout)

    def test_home_layout_rejects_unknown_widget_and_span(self):
        bad_type = {"mode": "custom", "widgets": [{"id": "w1", "type": "nope", "span": 1}]}
        bad_span = {"mode": "custom", "widgets": [{"id": "w1", "type": "news", "span": 5}]}
        self.assertEqual(self.client.put("/api/v1/home/layout", json=bad_type).status_code, 422)
        self.assertEqual(self.client.put("/api/v1/home/layout", json=bad_span).status_code, 422)

    def test_broken_stored_layout_falls_back_to_default(self):
        self.repo.user_settings[7] = {"home_layout": {"mode": "weird"}}
        self.assertEqual(
            self.client.get("/api/v1/home/layout").json(), {"mode": "unset", "widgets": []}
        )

    # ─── 설정
    def test_settings_defaults_match_mock_when_db_values_missing(self):
        self.repo.user_settings[7] = {"theme": None, "notify_email": None}
        res = self.client.get("/api/v1/settings")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), DEFAULT_SETTINGS)

    def test_settings_reads_db_values_over_defaults(self):
        self.repo.user_settings[7] = {
            "theme": "dark",
            "price_color": "green_up",
            "notify_email": False,
            "surge_threshold_pct": Decimal("10.00"),
            "quiet_start": time(23, 30),
            "ai_sensitivity": "strict",
        }
        self.repo.mcp_settings[7] = {"enabled": False, "scope_journal": False, "access": "read_write"}
        self.repo.mcp_apps[7] = [
            {
                "id": 3,
                "app_name": "Claude",
                "access": "read",
                "last_used_at": datetime(2026, 11, 20, 1, 0, tzinfo=timezone.utc),
            }
        ]
        body = self.client.get("/api/v1/settings").json()
        self.assertEqual(body["theme"], "dark")
        self.assertEqual(body["updown_color"], "green_up")
        self.assertFalse(body["notifications"]["channels"]["email"])
        self.assertEqual(body["notifications"]["price_spike_threshold"], 10)
        self.assertEqual(body["notifications"]["quiet_hours"], {"enabled": True, "from": "23:30", "to": "07:00"})
        self.assertEqual(body["ai"]["sensitivity"], "strict")
        self.assertFalse(body["mcp"]["enabled"])
        self.assertEqual(body["mcp"]["scopes"], {"memo": True, "journal": False, "stock": True})
        self.assertEqual(body["mcp"]["access"], "read_write")
        self.assertEqual(
            body["mcp"]["apps"],
            [{"id": "3", "name": "Claude", "access": "read", "last_used_at": "2026-11-20T01:00:00+00:00"}],
        )

    def test_settings_patch_writes_only_changed_columns(self):
        res = self.client.patch(
            "/api/v1/settings",
            json={
                "notifications": {"quiet_hours": {"from": "21:00"}, "price_spike_threshold": 3},
                "mcp": {"scopes": {"memo": False}, "server_url": "ignored", "apps": []},
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            self.repo.user_settings[7], {"quiet_start": time(21, 0), "surge_threshold_pct": 3}
        )
        self.assertEqual(self.repo.mcp_settings[7], {"scope_memos": False})
        body = res.json()
        self.assertEqual(body["notifications"]["quiet_hours"]["from"], "21:00")
        self.assertEqual(body["notifications"]["price_spike_threshold"], 3)
        self.assertFalse(body["mcp"]["scopes"]["memo"])
        self.assertEqual(body["mcp"]["server_url"], DEFAULT_SETTINGS["mcp"]["server_url"])

    def test_settings_patch_validates_values(self):
        for patch in (
            {"theme": "neon"},
            {"notifications": {"price_spike_threshold": 7}},
            {"notifications": {"quiet_hours": {"to": "25:00"}}},
            {"mcp": {"access": "admin"}},
        ):
            with self.subTest(patch=patch):
                self.assertEqual(self.client.patch("/api/v1/settings", json=patch).status_code, 422)

    # ─── 내 프로필
    def test_me_returns_frontend_user_shape(self):
        res = self.client.get("/api/v1/me")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json(),
            {
                "id": "7",
                "name": "서린",
                "bio": "",
                "avatar_url": None,
                "email": "u7@example.com",
                "providers": [
                    {"provider": "kakao", "email": "u7@example.com", "connected": True, "current": False}
                ],
                "plan": "free",
            },
        )

    def test_me_returns_plan_as_stored(self):
        for plan in ("free", "plus", "pro"):
            with self.subTest(plan=plan):
                self.repo.profiles[7]["plan"] = plan
                self.assertEqual(self.client.get("/api/v1/me").json()["plan"], plan)

    def test_me_patch_updates_name_and_bio(self):
        res = self.client.patch("/api/v1/me", json={"name": "  새 이름 ", "bio": "대학생"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["name"], "새 이름")
        self.assertEqual(res.json()["bio"], "대학생")
        self.assertEqual(self.client.get("/api/v1/me").json()["name"], "새 이름")

    def test_me_patch_rejects_blank_name_and_unknown_fields(self):
        self.assertEqual(self.client.patch("/api/v1/me", json={"name": "  "}).status_code, 422)
        self.assertEqual(self.client.patch("/api/v1/me", json={"email": "x@y.z"}).status_code, 422)

    def test_requires_authentication(self):
        app = FastAPI()
        app.include_router(router)
        # 토큰이 없으면 인증 서비스를 쓰기 전에 401 이 나야 한다.
        app.dependency_overrides[get_auth_service] = lambda: None
        app.dependency_overrides[get_account_query_service] = lambda: None
        client = TestClient(app)
        for method, path in (
            ("get", "/api/v1/home/layout"),
            ("get", "/api/v1/settings"),
            ("get", "/api/v1/me"),
        ):
            with self.subTest(path=path):
                self.assertEqual(getattr(client, method)(path).status_code, 401)


class RecordingSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))


class AccountRepositorySqlTest(unittest.TestCase):
    def test_upsert_user_settings_uses_on_conflict(self):
        session = RecordingSession()
        AccountRepository(session).upsert_user_settings(7, {"theme": "dark", "notify_news": False})
        sql, params = session.calls[0]
        self.assertIn("INSERT INTO user_settings (user_id, notify_news, theme)", sql)
        self.assertIn("ON CONFLICT (user_id) DO UPDATE", sql)
        self.assertEqual(params, {"user_id": 7, "theme": "dark", "notify_news": False})

    def test_unknown_columns_are_rejected(self):
        with self.assertRaises(ValueError):
            AccountRepository(RecordingSession()).upsert_user_settings(7, {"user_id; DROP": 1})
        with self.assertRaises(ValueError):
            AccountRepository(RecordingSession()).upsert_mcp_settings(7, {"server_url": "x"})

    def test_empty_patch_does_not_touch_db(self):
        session = RecordingSession()
        repo = AccountRepository(session)
        repo.upsert_user_settings(7, {})
        repo.update_profile(7, display_name=None, bio=None)
        self.assertEqual(session.calls, [])


if __name__ == "__main__":
    unittest.main()
