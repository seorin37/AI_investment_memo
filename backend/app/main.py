"""MEMO'S FastAPI application."""

import hmac
import os
import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.routes import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE, router as auth_router
from pipelines.common.db import DatabaseConfigError, get_read_dsn

load_dotenv()

app = FastAPI(title="Memos API")


def _allowed_origins() -> list[str]:
    configured = os.getenv("AUTH_CORS_ORIGINS", "")
    if configured.strip():
        return [value.strip().rstrip("/") for value in configured.split(",") if value.strip()]
    return ["http://localhost:8081", "http://127.0.0.1:8081"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def csrf_for_cookie_sessions(request: Request, call_next):
    """Double-submit CSRF protection for browser cookie authentication."""
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        uses_cookie_session = bool(
            request.cookies.get(ACCESS_COOKIE) or request.cookies.get(REFRESH_COOKIE)
        ) and not request.headers.get("authorization")
        if uses_cookie_session:
            cookie_value = request.cookies.get(CSRF_COOKIE, "")
            header_value = request.headers.get("x-csrf-token", "")
            if not cookie_value or not hmac.compare_digest(cookie_value, header_value):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF 검증에 실패했습니다."},
                )
    return await call_next(request)


app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    try:
        dsn = get_read_dsn()
        if not dsn:
            raise DatabaseConfigError(
                "READONLY_DATABASE_URL 또는 DATABASE_URL이 없습니다."
            )
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            row = conn.execute(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
        return {"status": "ok", "pgvector": row is not None}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": "database health check failed"},
        )
