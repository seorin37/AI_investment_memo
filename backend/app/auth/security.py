"""Small, auditable security primitives for PKCE and first-party HS256 JWTs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any


class TokenValidationError(ValueError):
    pass


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise TokenValidationError("잘못된 토큰 인코딩입니다.") from exc


def random_token(byte_length: int = 32) -> str:
    return b64url(secrets.token_bytes(byte_length))


def token_hash(value: str, secret: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def pkce_challenge(verifier: str) -> str:
    return b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def verify_pkce(verifier: str, expected_challenge: str) -> bool:
    return hmac.compare_digest(pkce_challenge(verifier), expected_challenge)


def _json_segment(value: dict[str, Any]) -> str:
    return b64url(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())


@dataclass(frozen=True)
class JwtCodec:
    secret: str
    issuer: str
    audience: str
    access_seconds: int = 900

    def issue_access(self, user_id: int, session_id: str, now: int | None = None) -> str:
        issued = int(time.time() if now is None else now)
        payload = {
            "sub": str(user_id),
            "sid": session_id,
            "typ": "access",
            "iss": self.issuer,
            "aud": self.audience,
            "iat": issued,
            "nbf": issued,
            "exp": issued + self.access_seconds,
            "jti": random_token(16),
        }
        head = _json_segment({"alg": "HS256", "typ": "JWT"})
        body = _json_segment(payload)
        signature = b64url(hmac.new(self.secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest())
        return f"{head}.{body}.{signature}"

    def decode_access(self, token: str, now: int | None = None) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise TokenValidationError("잘못된 JWT 형식입니다.")
        head_raw, body_raw, supplied = parts
        expected = b64url(
            hmac.new(self.secret.encode(), f"{head_raw}.{body_raw}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected, supplied):
            raise TokenValidationError("JWT 서명이 유효하지 않습니다.")
        try:
            header = json.loads(b64url_decode(head_raw))
            payload = json.loads(b64url_decode(body_raw))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise TokenValidationError("JWT 내용이 유효하지 않습니다.") from exc
        if header != {"alg": "HS256", "typ": "JWT"}:
            raise TokenValidationError("허용되지 않은 JWT 알고리즘입니다.")
        current = int(time.time() if now is None else now)
        required = ("sub", "sid", "typ", "iss", "aud", "iat", "nbf", "exp", "jti")
        if any(key not in payload for key in required):
            raise TokenValidationError("JWT 필수 클레임이 없습니다.")
        if payload["typ"] != "access" or payload["iss"] != self.issuer or payload["aud"] != self.audience:
            raise TokenValidationError("JWT 발급자 또는 대상이 올바르지 않습니다.")
        if not isinstance(payload["exp"], int) or payload["exp"] <= current:
            raise TokenValidationError("JWT가 만료되었습니다.")
        if not isinstance(payload["nbf"], int) or payload["nbf"] > current + 30:
            raise TokenValidationError("아직 사용할 수 없는 JWT입니다.")
        try:
            int(payload["sub"])
        except (TypeError, ValueError) as exc:
            raise TokenValidationError("JWT 사용자 식별자가 유효하지 않습니다.") from exc
        return payload
