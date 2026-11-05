from __future__ import annotations

import unittest

from app.auth.config import AuthConfigurationError, AuthSettings
from app.auth.security import JwtCodec, TokenValidationError, pkce_challenge, verify_pkce
from app.auth.service import AuthError, ensure_owner


class AuthConfigurationTest(unittest.TestCase):
    def test_requires_long_secret_and_exact_return_allowlists(self):
        env = {
            "AUTH_JWT_SECRET": "s" * 32,
            "AUTH_PUBLIC_BASE_URL": "https://api.example.test/",
            "AUTH_WEB_RETURN_URLS": "https://app.example.test/auth/callback",
            "AUTH_MOBILE_RETURN_URLS": "memos://auth/callback",
        }
        settings = AuthSettings.from_env(env)
        self.assertEqual(
            settings.validate_return_to("mobile", "memos://auth/callback"),
            "memos://auth/callback",
        )
        with self.assertRaises(ValueError):
            settings.validate_return_to("web", "https://evil.example/auth/callback")
        with self.assertRaises(AuthConfigurationError):
            AuthSettings.from_env({**env, "AUTH_JWT_SECRET": "short"})


class PkceTest(unittest.TestCase):
    def test_s256_verification(self):
        verifier = "v" * 64
        challenge = pkce_challenge(verifier)
        self.assertTrue(verify_pkce(verifier, challenge))
        self.assertFalse(verify_pkce("x" * 64, challenge))


class JwtTest(unittest.TestCase):
    def setUp(self):
        self.codec = JwtCodec("j" * 32, "issuer", "audience", 900)

    def test_valid_access_token(self):
        token = self.codec.issue_access(42, "83b41f02-3e74-41b1-8515-a97756c90d20", now=1_000)
        claims = self.codec.decode_access(token, now=1_100)
        self.assertEqual(claims["sub"], "42")
        self.assertEqual(claims["iss"], "issuer")

    def test_expired_and_tampered_tokens_are_rejected(self):
        token = self.codec.issue_access(42, "session", now=1_000)
        with self.assertRaises(TokenValidationError):
            self.codec.decode_access(token, now=1_901)
        changed = token[:-1] + ("A" if token[-1] != "A" else "B")
        with self.assertRaises(TokenValidationError):
            self.codec.decode_access(changed, now=1_100)

    def test_wrong_issuer_and_audience_are_rejected(self):
        token = self.codec.issue_access(42, "session", now=1_000)
        with self.assertRaises(TokenValidationError):
            JwtCodec("j" * 32, "other", "audience").decode_access(token, now=1_100)
        with self.assertRaises(TokenValidationError):
            JwtCodec("j" * 32, "issuer", "other").decode_access(token, now=1_100)


class OwnershipTest(unittest.TestCase):
    def test_only_authenticated_owner_is_accepted(self):
        ensure_owner("7", 7)
        with self.assertRaises(AuthError) as caught:
            ensure_owner(7, 8)
        self.assertEqual(caught.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
