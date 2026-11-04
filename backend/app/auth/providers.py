"""Official OAuth endpoints and provider-specific identity verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from .config import AuthConfigurationError, AuthSettings


class ProviderError(RuntimeError):
    """Sanitized provider failure; response bodies and tokens are never exposed."""


@dataclass(frozen=True)
class ProviderProfile:
    provider: str
    provider_user_id: str
    email: str | None
    display_name: str
    avatar_url: str | None


@dataclass(frozen=True)
class ProviderSpec:
    authorize_url: str
    token_url: str
    userinfo_url: str | None
    scopes: tuple[str, ...]
    supports_pkce: bool


SPECS = {
    "google": ProviderSpec(
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        None,
        ("openid", "email", "profile"),
        True,
    ),
    "kakao": ProviderSpec(
        "https://kauth.kakao.com/oauth/authorize",
        "https://kauth.kakao.com/oauth/token",
        "https://kapi.kakao.com/v2/user/me",
        ("profile_nickname", "profile_image", "account_email"),
        True,
    ),
    "naver": ProviderSpec(
        "https://nid.naver.com/oauth2.0/authorize",
        "https://nid.naver.com/oauth2.0/token",
        "https://openapi.naver.com/v1/nid/me",
        (),
        False,
    ),
}


def provider_names() -> tuple[str, ...]:
    return tuple(SPECS)


class OAuthProviderClient:
    def __init__(
        self,
        settings: AuthSettings,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._http = http

    def authorization_url(
        self,
        provider: str,
        *,
        state: str,
        redirect_uri: str,
        code_challenge: str | None,
        nonce: str | None,
    ) -> str:
        spec = self._spec(provider)
        credentials = self.settings.provider(provider)
        params: dict[str, str] = {
            "client_id": credentials.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        if spec.scopes:
            params["scope"] = ("," if provider == "kakao" else " ").join(spec.scopes)
        if spec.supports_pkce:
            if not code_challenge:
                raise ProviderError("PKCE 설정이 누락되었습니다.")
            params.update(code_challenge=code_challenge, code_challenge_method="S256")
        if provider == "google":
            params.update(access_type="online", include_granted_scopes="true")
        if nonce:
            params["nonce"] = nonce
        return f"{spec.authorize_url}?{urlencode(params)}"

    async def authenticate(
        self,
        provider: str,
        *,
        code: str,
        redirect_uri: str,
        code_verifier: str | None,
        state: str,
        nonce: str | None,
    ) -> ProviderProfile:
        spec = self._spec(provider)
        credentials = self.settings.provider(provider)
        form: dict[str, str] = {
            "grant_type": "authorization_code",
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        }
        if spec.supports_pkce and code_verifier:
            form["code_verifier"] = code_verifier
        if provider == "naver":
            form["state"] = state
        async with self._client() as client:
            try:
                response = await client.post(
                    spec.token_url,
                    data=form,
                    headers={"Accept": "application/json"},
                )
            except httpx.HTTPError as exc:
                raise ProviderError("OAuth 제공자 토큰 서버에 연결하지 못했습니다.") from exc
            if response.status_code != 200:
                raise ProviderError(f"OAuth 토큰 교환에 실패했습니다 ({response.status_code}).")
            token_data = self._json_object(response, "OAuth 토큰 응답")
            access_token = token_data.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise ProviderError("OAuth 토큰 응답에 access_token이 없습니다.")
            if provider == "google":
                id_token = token_data.get("id_token")
                if not isinstance(id_token, str) or not id_token:
                    raise ProviderError("Google OIDC ID Token이 없습니다.")
                claims = await self._verify_google_id_token(
                    client, id_token, credentials.client_id, nonce
                )
                return ProviderProfile(
                    provider="google",
                    provider_user_id=str(claims["sub"]),
                    email=_optional_text(claims.get("email")),
                    display_name=_optional_text(claims.get("name")) or "Google 사용자",
                    avatar_url=_optional_text(claims.get("picture")),
                )
            return await self._load_userinfo(client, provider, spec, access_token)

    async def _verify_google_id_token(
        self,
        client: httpx.AsyncClient,
        id_token: str,
        client_id: str,
        nonce: str | None,
    ) -> dict[str, Any]:
        try:
            import jwt
        except ImportError as exc:
            raise AuthConfigurationError(
                "Google OIDC 검증에 PyJWT[crypto] 패키지가 필요합니다."
            ) from exc
        try:
            header = jwt.get_unverified_header(id_token)
            response = await client.get("https://www.googleapis.com/oauth2/v3/certs")
            response.raise_for_status()
            jwks = self._json_object(response, "Google JWKS")
            keys = jwt.PyJWKSet.from_dict(jwks).keys
            key = next(item.key for item in keys if item.key_id == header.get("kid"))
            claims = jwt.decode(
                id_token,
                key,
                algorithms=["RS256"],
                audience=client_id,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except (httpx.HTTPError, StopIteration, ValueError, KeyError, jwt.PyJWTError) as exc:
            raise ProviderError("Google OIDC ID Token 검증에 실패했습니다.") from exc
        if claims.get("iss") not in {"https://accounts.google.com", "accounts.google.com"}:
            raise ProviderError("Google OIDC 발급자가 올바르지 않습니다.")
        if nonce and claims.get("nonce") != nonce:
            raise ProviderError("Google OIDC nonce 검증에 실패했습니다.")
        if claims.get("email") and claims.get("email_verified") is not True:
            raise ProviderError("Google 이메일이 검증되지 않았습니다.")
        return claims

    async def _load_userinfo(
        self,
        client: httpx.AsyncClient,
        provider: str,
        spec: ProviderSpec,
        access_token: str,
    ) -> ProviderProfile:
        assert spec.userinfo_url
        try:
            response = await client.get(
                spec.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise ProviderError("OAuth 사용자 정보 서버에 연결하지 못했습니다.") from exc
        if response.status_code != 200:
            raise ProviderError(f"OAuth 사용자 정보 조회에 실패했습니다 ({response.status_code}).")
        data = self._json_object(response, "OAuth 사용자 정보")
        if provider == "kakao":
            account = data.get("kakao_account") if isinstance(data.get("kakao_account"), dict) else {}
            profile = account.get("profile") if isinstance(account.get("profile"), dict) else {}
            uid = data.get("id")
            if uid is None:
                raise ProviderError("Kakao 사용자 식별자가 없습니다.")
            return ProviderProfile(
                provider=provider,
                provider_user_id=str(uid),
                email=_optional_text(account.get("email")),
                display_name=_optional_text(profile.get("nickname")) or "Kakao 사용자",
                avatar_url=_optional_text(profile.get("profile_image_url")),
            )
        wrapped = data.get("response")
        if not isinstance(wrapped, dict) or not wrapped.get("id"):
            raise ProviderError("Naver 사용자 식별자가 없습니다.")
        return ProviderProfile(
            provider=provider,
            provider_user_id=str(wrapped["id"]),
            email=_optional_text(wrapped.get("email")),
            display_name=_optional_text(wrapped.get("name")) or _optional_text(wrapped.get("nickname")) or "Naver 사용자",
            avatar_url=_optional_text(wrapped.get("profile_image")),
        )

    def _client(self):
        if self._http is not None:
            return _BorrowedClient(self._http)
        return httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=False)

    @staticmethod
    def _spec(provider: str) -> ProviderSpec:
        try:
            return SPECS[provider]
        except KeyError as exc:
            raise ProviderError("지원하지 않는 OAuth 제공자입니다.") from exc

    @staticmethod
    def _json_object(response: httpx.Response, label: str) -> dict[str, Any]:
        try:
            value = response.json()
        except ValueError as exc:
            raise ProviderError(f"{label} 형식이 올바르지 않습니다.") from exc
        if not isinstance(value, dict):
            raise ProviderError(f"{label} 형식이 올바르지 않습니다.")
        return value


class _BorrowedClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self.client

    async def __aexit__(self, *_args) -> None:
        return None


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
