from __future__ import annotations

import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.config import AuthSettings
from app.auth.routes import get_auth_service, router
from app.auth.service import CallbackResult, OAuthStart, SessionTokens


def settings() -> AuthSettings:
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


def tokens() -> SessionTokens:
    return SessionTokens(
        access_token="access-secret",
        refresh_token="refresh-secret",
        access_expires_in=900,
        refresh_expires_in=1_209_600,
        user={"id": "7", "name": "사용자", "bio": "", "avatar_url": None, "email": None, "providers": []},
        session_id=uuid4(),
    )


class FakeService:
    def __init__(self):
        self.settings = settings()

    def start_oauth(self, _provider, *, client_type, **_kwargs):
        return OAuthStart("https://provider.test/authorize?state=state-value", "state-value", client_type)

    async def complete_callback(self, _provider, **kwargs):
        if kwargs["state"] == "mobile-state":
            return CallbackResult("mobile", "memos://auth/callback", exchange_code="one-time-code")
        return CallbackResult("web", "https://app.example.test/auth/callback", tokens=tokens())

    def authenticate_access(self, value):
        if value != "valid-access":
            raise AssertionError("unexpected token")
        return tokens().user, tokens().session_id


class AuthApiContractTest(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.service = FakeService()
        app.dependency_overrides[get_auth_service] = lambda: self.service
        self.client = TestClient(app)

    def test_web_start_sets_http_only_state_cookie(self):
        response = self.client.get(
            "/api/v1/auth/google/start",
            params={"client": "web", "return_to": "https://app.example.test/auth/callback"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("state=state-value", response.headers["location"])
        cookie = response.headers["set-cookie"]
        self.assertIn("memos_oauth_state=", cookie)
        self.assertIn("HttpOnly", cookie)

    def test_mobile_callback_contains_only_one_time_code(self):
        response = self.client.get(
            "/api/v1/auth/kakao/callback",
            params={"state": "mobile-state", "code": "provider-code"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "memos://auth/callback?code=one-time-code")
        self.assertNotIn("access-secret", response.headers["location"])
        self.assertNotIn("refresh-secret", response.headers["location"])

    def test_web_callback_uses_http_only_tokens_and_safe_url(self):
        response = self.client.get(
            "/api/v1/auth/google/callback",
            params={"state": "web-state", "code": "provider-code"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "https://app.example.test/auth/callback?status=success")
        cookies = response.headers.get_list("set-cookie")
        self.assertTrue(any("memos_access=access-secret" in item and "HttpOnly" in item for item in cookies))
        self.assertTrue(any("memos_refresh=refresh-secret" in item and "HttpOnly" in item for item in cookies))
        self.assertNotIn("access-secret", response.headers["location"])

    def test_me_accepts_bearer_token(self):
        response = self.client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer valid-access"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "7")

    def test_me_without_authentication_is_rejected(self):
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "인증이 필요합니다.")


if __name__ == "__main__":
    unittest.main()
