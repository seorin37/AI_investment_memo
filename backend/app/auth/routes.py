"""FastAPI routes for browser cookies and Android one-time-code exchange."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db

from .config import AuthConfigurationError, AuthSettings
from .repository import AuthRepository
from .service import AuthError, AuthService, SessionTokens


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

ACCESS_COOKIE = "memos_access"
REFRESH_COOKIE = "memos_refresh"
CSRF_COOKIE = "memos_csrf"
OAUTH_STATE_COOKIE = "memos_oauth_state"


class MobileExchangeRequest(BaseModel):
    code: str = Field(min_length=20, max_length=256)
    code_verifier: str = Field(min_length=43, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str | None
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    user: dict


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    return AuthSettings.from_env()


def get_auth_service(
    db: Session = Depends(get_db), settings: AuthSettings = Depends(get_auth_settings)
) -> AuthService:
    return AuthService(AuthRepository(db), settings)


@router.get("/{provider}/start")
def start_oauth(
    provider: str,
    request: Request,
    client: str = Query(pattern="^(web|mobile)$"),
    return_to: str = Query(),
    code_challenge: str | None = Query(default=None),
    service: AuthService = Depends(get_auth_service),
):
    try:
        result = service.start_oauth(
            provider,
            client_type=client,
            return_to=return_to,
            app_code_challenge=code_challenge,
        )
        response = RedirectResponse(result.url, status_code=302)
        if result.client_type == "web":
            response.set_cookie(
                OAUTH_STATE_COOKIE,
                result.state,
                httponly=True,
                secure=service.settings.cookie_secure,
                samesite=service.settings.cookie_samesite,
                max_age=service.settings.oauth_state_minutes * 60,
                path="/api/v1/auth",
                domain=service.settings.cookie_domain,
            )
        return response
    except (AuthError, AuthConfigurationError) as exc:
        _raise_safe(exc)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    state: str = Query(default=""),
    code: str = Query(default=""),
    error: str | None = Query(default=None),
    service: AuthService = Depends(get_auth_service),
):
    try:
        if error or not code:
            return_to = service.consume_failed_callback(
                provider, state, request.cookies.get(OAUTH_STATE_COOKIE)
            )
            response = RedirectResponse(f"{return_to}?{urlencode({'error': 'oauth_cancelled'})}", 302)
            _clear_oauth_state(response, service.settings)
            return response
        result = await service.complete_callback(
            provider,
            state=state,
            code=code,
            user_agent=request.headers.get("user-agent"),
            web_state_cookie=request.cookies.get(OAUTH_STATE_COOKIE),
        )
        if result.client_type == "mobile":
            return RedirectResponse(
                f"{result.return_to}?{urlencode({'code': result.exchange_code})}", 302
            )
        response = RedirectResponse(
            f"{result.return_to}?{urlencode({'status': 'success'})}", 302
        )
        assert result.tokens
        _set_web_cookies(response, result.tokens, service.settings)
        _clear_oauth_state(response, service.settings)
        return response
    except (AuthError, AuthConfigurationError) as exc:
        _raise_safe(exc)


@router.post("/mobile/exchange", response_model=TokenResponse)
def mobile_exchange(
    payload: MobileExchangeRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    try:
        tokens = service.exchange_mobile_code(
            payload.code, payload.code_verifier, request.headers.get("user-agent")
        )
        return _token_response(tokens, include_refresh=True)
    except AuthError as exc:
        _raise_safe(exc)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    refresh_token = payload.refresh_token or request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(401, detail="Refresh Token이 없습니다.")
    try:
        tokens = service.refresh_session(refresh_token, request.headers.get("user-agent"))
        is_web = payload.refresh_token is None
        if is_web:
            _set_web_cookies(response, tokens, service.settings)
        return _token_response(tokens, include_refresh=not is_web)
    except AuthError as exc:
        _clear_web_cookies(response, service.settings)
        _raise_safe(exc)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    service: AuthService = Depends(get_auth_service),
):
    service.logout(
        access_token=_access_token(request),
        refresh_token=(payload.refresh_token if payload else None)
        or request.cookies.get(REFRESH_COOKIE),
    )
    _clear_web_cookies(response, service.settings)
    response.status_code = 204


def get_current_user(
    request: Request, service: AuthService = Depends(get_auth_service)
) -> dict:
    token = _access_token(request)
    if not token:
        raise HTTPException(401, detail="인증이 필요합니다.")
    try:
        user, _session_id = service.authenticate_access(token)
        return user
    except AuthError as exc:
        _raise_safe(exc)


@router.get("/me", name="auth_me")
def authenticated_me(current: dict = Depends(get_current_user)) -> dict:
    return current


def _access_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return request.cookies.get(ACCESS_COOKIE)


def _token_response(tokens: SessionTokens, *, include_refresh: bool) -> dict:
    return {
        "access_token": tokens.access_token if include_refresh else None,
        "refresh_token": tokens.refresh_token if include_refresh else None,
        "token_type": "bearer",
        "expires_in": tokens.access_expires_in,
        "user": tokens.user,
    }


def _set_web_cookies(response: Response, tokens: SessionTokens, settings: AuthSettings) -> None:
    common = {
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "domain": settings.cookie_domain,
    }
    response.set_cookie(
        ACCESS_COOKIE,
        tokens.access_token,
        httponly=True,
        max_age=tokens.access_expires_in,
        path="/",
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        httponly=True,
        max_age=tokens.refresh_expires_in,
        path="/api/v1/auth",
        **common,
    )
    from .security import random_token

    response.set_cookie(
        CSRF_COOKIE,
        random_token(24),
        httponly=False,
        max_age=tokens.refresh_expires_in,
        path="/",
        **common,
    )


def _clear_web_cookies(response: Response, settings: AuthSettings) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=settings.cookie_domain)
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth", domain=settings.cookie_domain)
    response.delete_cookie(CSRF_COOKIE, path="/", domain=settings.cookie_domain)


def _clear_oauth_state(response: Response, settings: AuthSettings) -> None:
    response.delete_cookie(
        OAUTH_STATE_COOKIE, path="/api/v1/auth", domain=settings.cookie_domain
    )


def _raise_safe(exc: Exception):
    if isinstance(exc, AuthError):
        raise HTTPException(exc.status_code, detail=str(exc)) from exc
    raise HTTPException(503, detail="인증 서비스 설정이 완료되지 않았습니다.") from exc
