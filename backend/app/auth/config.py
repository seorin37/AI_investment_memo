"""Authentication settings loaded only from server-side environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


class AuthConfigurationError(RuntimeError):
    """Safe configuration error that never includes a secret value."""


def _csv(value: str | None) -> tuple[str, ...]:
    return tuple(part.strip().rstrip("/") for part in (value or "").split(",") if part.strip())


def _required(environ: dict[str, str] | os._Environ[str], key: str) -> str:
    value = environ.get(key, "").strip()
    if not value:
        raise AuthConfigurationError(f"필수 인증 환경변수 {key}가 설정되지 않았습니다.")
    return value


@dataclass(frozen=True)
class ProviderSettings:
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class AuthSettings:
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    public_base_url: str
    web_return_urls: tuple[str, ...]
    mobile_return_urls: tuple[str, ...]
    cookie_secure: bool
    cookie_samesite: str
    cookie_domain: str | None
    access_minutes: int = 15
    refresh_days: int = 14
    oauth_state_minutes: int = 10
    exchange_code_minutes: int = 3

    @classmethod
    def from_env(cls, environ=None) -> "AuthSettings":
        env = os.environ if environ is None else environ
        secret = _required(env, "AUTH_JWT_SECRET")
        if len(secret.encode("utf-8")) < 32:
            raise AuthConfigurationError("AUTH_JWT_SECRET은 최소 32바이트여야 합니다.")
        public = _required(env, "AUTH_PUBLIC_BASE_URL").rstrip("/")
        web = _csv(env.get("AUTH_WEB_RETURN_URLS"))
        mobile = _csv(env.get("AUTH_MOBILE_RETURN_URLS"))
        if not web or not mobile:
            raise AuthConfigurationError(
                "AUTH_WEB_RETURN_URLS와 AUTH_MOBILE_RETURN_URLS를 모두 설정해야 합니다."
            )
        secure = env.get("AUTH_COOKIE_SECURE", "true").lower() == "true"
        same_site = env.get("AUTH_COOKIE_SAMESITE", "lax").strip().lower() or "lax"
        if same_site not in {"lax", "strict", "none"}:
            raise AuthConfigurationError("AUTH_COOKIE_SAMESITE 값이 올바르지 않습니다.")
        if same_site == "none" and not secure:
            raise AuthConfigurationError("SameSite=None 쿠키에는 Secure 설정이 필요합니다.")
        return cls(
            jwt_secret=secret,
            jwt_issuer=env.get("AUTH_JWT_ISSUER", "memos-api").strip() or "memos-api",
            jwt_audience=env.get("AUTH_JWT_AUDIENCE", "memos-app").strip() or "memos-app",
            public_base_url=public,
            web_return_urls=web,
            mobile_return_urls=mobile,
            cookie_secure=secure,
            cookie_samesite=same_site,
            cookie_domain=env.get("AUTH_COOKIE_DOMAIN", "").strip() or None,
        )

    def provider(self, name: str, environ=None) -> ProviderSettings:
        env = os.environ if environ is None else environ
        prefix = name.upper()
        return ProviderSettings(
            client_id=_required(env, f"{prefix}_OAUTH_CLIENT_ID"),
            client_secret=_required(env, f"{prefix}_OAUTH_CLIENT_SECRET"),
        )

    def validate_return_to(self, client_type: str, return_to: str) -> str:
        normalized = return_to.rstrip("/")
        allowed = self.web_return_urls if client_type == "web" else self.mobile_return_urls
        if normalized not in allowed:
            raise ValueError("허용되지 않은 인증 복귀 주소입니다.")
        return normalized

    def provider_callback(self, provider: str) -> str:
        return f"{self.public_base_url}/api/v1/auth/{provider}/callback"
