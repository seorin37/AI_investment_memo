from __future__ import annotations

import unittest
import json
import time
from unittest import mock

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.config import AuthSettings
from app.auth.providers import OAuthProviderClient


def settings() -> AuthSettings:
    return AuthSettings.from_env(
        {
            "AUTH_JWT_SECRET": "s" * 32,
            "AUTH_PUBLIC_BASE_URL": "https://api.example.test",
            "AUTH_WEB_RETURN_URLS": "https://app.example.test/auth/callback",
            "AUTH_MOBILE_RETURN_URLS": "memos://auth/callback",
        }
    )


class OAuthProviderTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env = {
            "KAKAO_OAUTH_CLIENT_ID": "kakao-client",
            "KAKAO_OAUTH_CLIENT_SECRET": "kakao-secret",
            "NAVER_OAUTH_CLIENT_ID": "naver-client",
            "NAVER_OAUTH_CLIENT_SECRET": "naver-secret",
            "GOOGLE_OAUTH_CLIENT_ID": "google-client",
            "GOOGLE_OAUTH_CLIENT_SECRET": "google-secret",
        }

    def test_authorization_url_uses_state_pkce_and_never_secret(self):
        client = OAuthProviderClient(settings())
        with mock.patch.dict("os.environ", self.env, clear=False):
            url = client.authorization_url(
                "kakao",
                state="state-value",
                redirect_uri="https://api.example.test/api/v1/auth/kakao/callback",
                code_challenge="challenge",
                nonce=None,
            )
        self.assertIn("state=state-value", url)
        self.assertIn("code_challenge=challenge", url)
        self.assertNotIn("kakao-secret", url)

    async def test_kakao_token_and_userinfo_are_mapped_without_leaking_token(self):
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if request.url.host == "kauth.kakao.com":
                return httpx.Response(200, json={"access_token": "provider-token"})
            return httpx.Response(
                200,
                json={
                    "id": 12345,
                    "kakao_account": {
                        "email": "user@example.test",
                        "profile": {"nickname": "테스트", "profile_image_url": "https://img.test/a"},
                    },
                },
            )

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = OAuthProviderClient(settings(), http=http)
        with mock.patch.dict("os.environ", self.env, clear=False):
            profile = await client.authenticate(
                "kakao",
                code="provider-code",
                redirect_uri="https://api.example.test/api/v1/auth/kakao/callback",
                code_verifier="v" * 64,
                state="state",
                nonce=None,
            )
        await http.aclose()
        self.assertEqual(profile.provider_user_id, "12345")
        self.assertEqual(profile.email, "user@example.test")
        self.assertEqual(len(calls), 2)

    async def test_naver_identity_mapping(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "nid.naver.com":
                return httpx.Response(200, json={"access_token": "provider-token"})
            return httpx.Response(200, json={"response": {"id": "naver-id", "nickname": "네이버"}})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = OAuthProviderClient(settings(), http=http)
        with mock.patch.dict("os.environ", self.env, clear=False):
            profile = await client.authenticate(
                "naver",
                code="code",
                redirect_uri="https://api.example.test/api/v1/auth/naver/callback",
                code_verifier=None,
                state="state",
                nonce=None,
            )
        await http.aclose()
        self.assertEqual(profile.provider_user_id, "naver-id")
        self.assertEqual(profile.display_name, "네이버")

    async def test_google_oidc_signature_audience_issuer_and_nonce(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
        public_jwk["kid"] = "test-key"
        now = int(time.time())
        id_token = jwt.encode(
            {
                "sub": "google-user",
                "iss": "https://accounts.google.com",
                "aud": "google-client",
                "iat": now,
                "exp": now + 300,
                "nonce": "expected-nonce",
                "email": "google@example.test",
                "email_verified": True,
                "name": "Google 사용자",
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "oauth2.googleapis.com":
                return httpx.Response(200, json={"access_token": "provider-token", "id_token": id_token})
            if request.url.host == "www.googleapis.com":
                return httpx.Response(200, json={"keys": [public_jwk]})
            raise AssertionError(f"unexpected request: {request.url}")

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = OAuthProviderClient(settings(), http=http)
        with mock.patch.dict("os.environ", self.env, clear=False):
            profile = await client.authenticate(
                "google",
                code="code",
                redirect_uri="https://api.example.test/api/v1/auth/google/callback",
                code_verifier="v" * 64,
                state="state",
                nonce="expected-nonce",
            )
        await http.aclose()
        self.assertEqual(profile.provider_user_id, "google-user")
        self.assertEqual(profile.email, "google@example.test")


if __name__ == "__main__":
    unittest.main()
