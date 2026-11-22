"""OAuth orchestration and first-party refresh-token rotation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from .config import AuthSettings
from .providers import OAuthProviderClient, ProviderError, provider_names
from .repository import AuthRepository
from .security import JwtCodec, TokenValidationError, pkce_challenge, random_token, token_hash, verify_pkce


class AuthError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int
    user: dict[str, Any]
    session_id: UUID


@dataclass(frozen=True)
class CallbackResult:
    client_type: str
    return_to: str
    tokens: SessionTokens | None = None
    exchange_code: str | None = None


@dataclass(frozen=True)
class OAuthStart:
    url: str
    state: str
    client_type: str


class AuthService:
    def __init__(
        self,
        repository: AuthRepository,
        settings: AuthSettings,
        provider_client: OAuthProviderClient | None = None,
    ) -> None:
        self.repo = repository
        self.settings = settings
        self.providers = provider_client or OAuthProviderClient(settings)
        self.jwt = JwtCodec(
            settings.jwt_secret,
            settings.jwt_issuer,
            settings.jwt_audience,
            settings.access_minutes * 60,
        )

    def start_oauth(
        self,
        provider: str,
        *,
        client_type: str,
        return_to: str,
        app_code_challenge: str | None,
    ) -> OAuthStart:
        if provider not in provider_names():
            raise AuthError("unsupported_provider", "지원하지 않는 로그인 제공자입니다.", 404)
        if client_type not in {"web", "mobile"}:
            raise AuthError("invalid_client", "지원하지 않는 인증 클라이언트입니다.", 400)
        try:
            safe_return = self.settings.validate_return_to(client_type, return_to)
        except ValueError as exc:
            raise AuthError("invalid_return_uri", str(exc), 400) from exc
        if client_type == "mobile" and (
            not app_code_challenge
            or re.fullmatch(r"[A-Za-z0-9_-]{43,128}", app_code_challenge) is None
        ):
            raise AuthError("pkce_required", "모바일 인증에는 유효한 PKCE challenge가 필요합니다.", 400)
        state = random_token()
        provider_verifier = random_token(48)
        nonce = random_token()
        callback = self.settings.provider_callback(provider)
        self.repo.create_oauth_transaction(
            {
                "state_hash": token_hash(state, self.settings.jwt_secret),
                "provider": provider,
                "client_type": client_type,
                "return_to": safe_return,
                "provider_redirect_uri": callback,
                "provider_code_verifier": provider_verifier,
                "oidc_nonce": nonce if provider == "google" else None,
                "app_code_challenge": app_code_challenge,
                "expires_at": datetime.now(timezone.utc)
                + timedelta(minutes=self.settings.oauth_state_minutes),
            }
        )
        return OAuthStart(
            url=self.providers.authorization_url(
                provider,
                state=state,
                redirect_uri=callback,
                code_challenge=pkce_challenge(provider_verifier),
                nonce=nonce if provider == "google" else None,
            ),
            state=state,
            client_type=client_type,
        )

    def consume_failed_callback(
        self, provider: str, state: str, web_state_cookie: str | None
    ) -> str:
        transaction = self._consume_state(provider, state, web_state_cookie)
        return str(transaction["return_to"])

    async def complete_callback(
        self,
        provider: str,
        *,
        state: str,
        code: str,
        user_agent: str | None,
        web_state_cookie: str | None,
    ) -> CallbackResult:
        transaction = self._consume_state(provider, state, web_state_cookie)
        # Commit state consumption before the external token exchange so the same
        # callback cannot be raced or replayed even if the provider is unavailable.
        self.repo.db.commit()
        try:
            profile = await self.providers.authenticate(
                provider,
                code=code,
                redirect_uri=str(transaction["provider_redirect_uri"]),
                code_verifier=transaction.get("provider_code_verifier"),
                state=state,
                nonce=transaction.get("oidc_nonce"),
            )
        except ProviderError as exc:
            raise AuthError("provider_auth_failed", str(exc), 401) from exc
        user = self.repo.get_or_create_user(profile)
        self._ensure_active(user)
        if transaction["client_type"] == "web":
            tokens = self.issue_session(user, user_agent=user_agent)
            return CallbackResult("web", str(transaction["return_to"]), tokens=tokens)
        exchange_code = random_token()
        self.repo.create_exchange_code(
            {
                "code_hash": token_hash(exchange_code, self.settings.jwt_secret),
                "user_id": user["id"],
                "code_challenge": transaction["app_code_challenge"],
                "expires_at": datetime.now(timezone.utc)
                + timedelta(minutes=self.settings.exchange_code_minutes),
            }
        )
        return CallbackResult(
            "mobile", str(transaction["return_to"]), exchange_code=exchange_code
        )

    def exchange_mobile_code(
        self, code: str, verifier: str, user_agent: str | None
    ) -> SessionTokens:
        record = self.repo.consume_exchange_code(token_hash(code, self.settings.jwt_secret))
        if not record or not verify_pkce(verifier, record["code_challenge"]):
            raise AuthError("invalid_exchange_code", "교환 코드 또는 PKCE 검증에 실패했습니다.")
        user = self._user_without_session(int(record["user_id"]))
        self._ensure_active(user)
        return self.issue_session(user, user_agent=user_agent)

    def issue_session(
        self,
        user: dict[str, Any],
        *,
        user_agent: str | None,
        family_id: UUID | None = None,
    ) -> SessionTokens:
        self._ensure_active(user)
        session_id = uuid4()
        family = family_id or uuid4()
        refresh = random_token(48)
        refresh_seconds = self.settings.refresh_days * 86400
        self.repo.insert_session(
            {
                "id": session_id,
                "family_id": family,
                "user_id": user["id"],
                "refresh_token_hash": token_hash(refresh, self.settings.jwt_secret),
                "user_agent_hash": _user_agent_hash(user_agent),
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=refresh_seconds),
            }
        )
        access = self.jwt.issue_access(int(user["id"]), str(session_id))
        return SessionTokens(
            access,
            refresh,
            self.settings.access_minutes * 60,
            refresh_seconds,
            _public_user(user),
            session_id,
        )

    def refresh_session(self, refresh_token: str, user_agent: str | None) -> SessionTokens:
        value_hash = token_hash(refresh_token, self.settings.jwt_secret)
        current = self.repo.lock_session_by_refresh_hash(value_hash)
        if not current:
            raise AuthError("invalid_refresh_token", "Refresh Token이 유효하지 않습니다.")
        if current["revoked_at"] is not None:
            self.repo.revoke_family(current["family_id"], "refresh_reuse_detected")
            self.repo.db.commit()
            raise AuthError("refresh_reuse_detected", "폐기된 Refresh Token 재사용이 감지되었습니다.")
        if current["expires_at"] <= datetime.now(timezone.utc):
            self.repo.revoke_family(current["family_id"], "expired")
            self.repo.db.commit()
            raise AuthError("refresh_expired", "Refresh Token이 만료되었습니다.")
        user = self._user_without_session(int(current["user_id"]))
        self._ensure_active(user)
        replacement = self._new_session_values(
            user_id=int(current["user_id"]),
            family_id=current["family_id"],
            user_agent=user_agent,
        )
        self.repo.rotate_session(current["id"], replacement[0])
        access = self.jwt.issue_access(int(user["id"]), str(replacement[0]["id"]))
        return SessionTokens(
            access,
            replacement[1],
            self.settings.access_minutes * 60,
            self.settings.refresh_days * 86400,
            _public_user(user),
            replacement[0]["id"],
        )

    def authenticate_access(self, token: str) -> tuple[dict[str, Any], UUID]:
        try:
            claims = self.jwt.decode_access(token)
            session_id = UUID(str(claims["sid"]))
        except (TokenValidationError, ValueError) as exc:
            raise AuthError("invalid_access_token", "Access Token이 유효하지 않습니다.") from exc
        user = self.repo.get_active_user_for_session(int(claims["sub"]), session_id)
        if not user:
            raise AuthError("session_revoked", "인증 세션이 만료되었거나 폐기되었습니다.")
        return _public_user(user), session_id

    def logout(self, *, access_token: str | None, refresh_token: str | None) -> None:
        if access_token:
            try:
                claims = self.jwt.decode_access(access_token)
                self.repo.revoke_session(UUID(str(claims["sid"])))
                return
            except (TokenValidationError, ValueError):
                pass
        if refresh_token:
            record = self.repo.lock_session_by_refresh_hash(
                token_hash(refresh_token, self.settings.jwt_secret)
            )
            if record:
                self.repo.revoke_session(record["id"])

    def _consume_state(
        self, provider: str, state: str, web_state_cookie: str | None
    ) -> dict[str, Any]:
        if provider not in provider_names() or not state:
            raise AuthError("invalid_oauth_state", "OAuth state가 유효하지 않습니다.", 400)
        transaction = self.repo.consume_oauth_transaction(
            token_hash(state, self.settings.jwt_secret)
        )
        if not transaction or transaction["provider"] != provider:
            raise AuthError("invalid_oauth_state", "OAuth state가 만료되었거나 재사용되었습니다.", 400)
        if transaction["client_type"] == "web" and web_state_cookie != state:
            raise AuthError("invalid_oauth_state", "OAuth 브라우저 state 검증에 실패했습니다.", 400)
        return transaction

    def _user_without_session(self, user_id: int) -> dict[str, Any]:
        user = self.repo.get_user(user_id)
        if not user:
            raise AuthError("user_not_found", "사용자 계정을 찾을 수 없습니다.")
        return user

    @staticmethod
    def _ensure_active(user: dict[str, Any]) -> None:
        if user.get("deleted_at") is not None:
            raise AuthError("inactive_user", "비활성화된 사용자입니다.", 403)

    def _new_session_values(
        self, *, user_id: int, family_id: UUID, user_agent: str | None
    ) -> tuple[dict[str, Any], str]:
        refresh = random_token(48)
        return (
            {
                "id": uuid4(),
                "family_id": family_id,
                "user_id": user_id,
                "refresh_token_hash": token_hash(refresh, self.settings.jwt_secret),
                "user_agent_hash": _user_agent_hash(user_agent),
                "expires_at": datetime.now(timezone.utc)
                + timedelta(days=self.settings.refresh_days),
            },
            refresh,
        )


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(user["id"]),
        "name": user.get("display_name") or "사용자",
        "bio": user.get("bio") or "",
        "avatar_url": user.get("avatar_url"),
        "email": user.get("email"),
        "providers": user.get("providers", []),
        # users.plan (plan_type: free·plus·pro) 그대로. 행에 없으면 무료
        "plan": str(user.get("plan") or "free"),
    }


def _user_agent_hash(value: str | None) -> str | None:
    return hashlib.sha256(value.encode()).hexdigest() if value else None


def ensure_owner(current_user_id: int | str, owner_user_id: int | str) -> None:
    """Reusable object-level ownership guard for future user-scoped CRUD."""
    if str(current_user_id) != str(owner_user_id):
        raise AuthError("forbidden", "다른 사용자의 데이터에 접근할 수 없습니다.", 403)
