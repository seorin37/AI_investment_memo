from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

from app.auth.config import AuthSettings
from app.auth.providers import ProviderProfile
from app.auth.security import pkce_challenge, token_hash
from app.auth.service import AuthError, AuthService, _public_user


class FakeDb:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class FakeRepository:
    def __init__(self):
        self.db = FakeDb()
        self.transactions = {}
        self.exchange_codes = {}
        self.sessions = {}
        self.user = {
            "id": 7,
            "email": "user@example.test",
            "display_name": "사용자",
            "bio": "",
            "avatar_url": None,
            "deleted_at": None,
            "providers": [],
        }

    def create_oauth_transaction(self, values):
        self.transactions[values["state_hash"]] = {**values, "consumed_at": None}

    def consume_oauth_transaction(self, value):
        row = self.transactions.get(value)
        if not row or row["consumed_at"] is not None:
            return None
        row["consumed_at"] = datetime.now(timezone.utc)
        return dict(row)

    def get_or_create_user(self, _profile):
        return dict(self.user)

    def create_exchange_code(self, values):
        self.exchange_codes[values["code_hash"]] = {**values, "used_at": None}

    def consume_exchange_code(self, value):
        row = self.exchange_codes.get(value)
        if not row or row["used_at"] is not None:
            return None
        row["used_at"] = datetime.now(timezone.utc)
        return dict(row)

    def insert_session(self, values):
        self.sessions[values["refresh_token_hash"]] = {**values, "revoked_at": None}

    def lock_session_by_refresh_hash(self, value):
        row = self.sessions.get(value)
        return dict(row) if row else None

    def rotate_session(self, old_id, values):
        for row in self.sessions.values():
            if row["id"] == old_id:
                row["revoked_at"] = datetime.now(timezone.utc)
                row["revoke_reason"] = "rotated"
                row["replaced_by"] = values["id"]
        self.insert_session(values)

    def revoke_family(self, family_id, reason):
        for row in self.sessions.values():
            if row["family_id"] == family_id:
                row["revoked_at"] = row.get("revoked_at") or datetime.now(timezone.utc)
                row["revoke_reason"] = row.get("revoke_reason") or reason

    def revoke_session(self, session_id, reason="logout"):
        for row in self.sessions.values():
            if row["id"] == session_id:
                row["revoked_at"] = datetime.now(timezone.utc)

    def list_identities(self, _user_id):
        return []

    def get_user(self, user_id):
        return dict(self.user) if user_id == self.user["id"] else None

    def get_active_user_for_session(self, user_id, session_id):
        active = any(
            row["id"] == session_id
            and row["user_id"] == user_id
            and row.get("revoked_at") is None
            for row in self.sessions.values()
        )
        return dict(self.user) if active and self.user["deleted_at"] is None else None


class FakeProvider:
    def authorization_url(self, _provider, **kwargs):
        return "https://provider.test/authorize?state=" + kwargs["state"]

    async def authenticate(self, provider, **_kwargs):
        return ProviderProfile(provider, "provider-user", "user@example.test", "사용자", None)


def auth_settings():
    return AuthSettings(
        jwt_secret="s" * 32,
        jwt_issuer="issuer",
        jwt_audience="audience",
        public_base_url="https://api.example.test",
        web_return_urls=("https://app.example.test/auth/callback",),
        mobile_return_urls=("memos://auth/callback",),
        cookie_secure=True,
        cookie_samesite="lax",
        cookie_domain=None,
    )


class AuthServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo = FakeRepository()
        self.service = AuthService(self.repo, auth_settings(), FakeProvider())

    def test_mobile_start_requires_valid_pkce(self):
        with mock.patch.dict("os.environ", {"GOOGLE_OAUTH_CLIENT_ID": "id", "GOOGLE_OAUTH_CLIENT_SECRET": "secret"}):
            with self.assertRaises(AuthError):
                self.service.start_oauth("google", client_type="mobile", return_to="memos://auth/callback", app_code_challenge=None)

    async def test_state_cookie_and_replay_are_rejected(self):
        with mock.patch.dict("os.environ", {"GOOGLE_OAUTH_CLIENT_ID": "id", "GOOGLE_OAUTH_CLIENT_SECRET": "secret"}):
            started = self.service.start_oauth("google", client_type="web", return_to="https://app.example.test/auth/callback", app_code_challenge=None)
        with self.assertRaises(AuthError):
            await self.service.complete_callback("google", state=started.state, code="code", user_agent=None, web_state_cookie="forged")

    async def test_mobile_code_is_single_use_and_pkce_bound(self):
        verifier = "v" * 64
        with mock.patch.dict("os.environ", {"KAKAO_OAUTH_CLIENT_ID": "id", "KAKAO_OAUTH_CLIENT_SECRET": "secret"}):
            started = self.service.start_oauth("kakao", client_type="mobile", return_to="memos://auth/callback", app_code_challenge=pkce_challenge(verifier))
        completed = await self.service.complete_callback("kakao", state=started.state, code="code", user_agent="agent", web_state_cookie=None)
        self.assertIsNone(completed.tokens)
        tokens = self.service.exchange_mobile_code(completed.exchange_code, verifier, "agent")
        self.assertEqual(tokens.user["id"], "7")
        with self.assertRaises(AuthError):
            self.service.exchange_mobile_code(completed.exchange_code, verifier, "agent")

    def test_refresh_rotation_and_reuse_revoke_family(self):
        initial = self.service.issue_session(self.repo.user, user_agent="agent")
        rotated = self.service.refresh_session(initial.refresh_token, "agent")
        self.assertNotEqual(rotated.refresh_token, initial.refresh_token)
        with self.assertRaises(AuthError) as caught:
            self.service.refresh_session(initial.refresh_token, "agent")
        self.assertEqual(caught.exception.code, "refresh_reuse_detected")
        with self.assertRaises(AuthError):
            self.service.refresh_session(rotated.refresh_token, "agent")

    def test_revoked_session_and_inactive_user_are_denied(self):
        tokens = self.service.issue_session(self.repo.user, user_agent=None)
        self.repo.revoke_session(tokens.session_id)
        with self.assertRaises(AuthError):
            self.service.authenticate_access(tokens.access_token)
        self.repo.user["deleted_at"] = datetime.now(timezone.utc)
        with self.assertRaises(AuthError):
            self.service.issue_session(self.repo.user, user_agent=None)

    def test_session_and_access_user_carry_plan(self):
        # 로그인 응답(tokens.user)과 /auth/me(authenticate_access)가 같은 plan 을 준다
        self.repo.user["plan"] = "plus"
        tokens = self.service.issue_session(self.repo.user, user_agent=None)
        self.assertEqual(tokens.user["plan"], "plus")
        user, _sid = self.service.authenticate_access(tokens.access_token)
        self.assertEqual(user["plan"], "plus")


class PublicUserPlanTest(unittest.TestCase):
    def test_plan_passes_through_and_defaults_to_free(self):
        base = {"id": 7, "display_name": "사용자"}
        for plan in ("free", "plus", "pro"):
            with self.subTest(plan=plan):
                self.assertEqual(_public_user({**base, "plan": plan})["plan"], plan)
        self.assertEqual(_public_user(base)["plan"], "free")
        self.assertEqual(_public_user({**base, "plan": None})["plan"], "free")


if __name__ == "__main__":
    unittest.main()
