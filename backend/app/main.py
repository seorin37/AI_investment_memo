"""MEMO'S FastAPI application."""

import hmac
import os
import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.account.routes import router as account_router
from app.auth.routes import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE, router as auth_router
from app.board.routes import router as board_router
from app.marketdata.routes import router as marketdata_router
from app.updates.routes import router as updates_router
from app.credits.routes import router as credits_router
from app.stocks.routes import router as stocks_router
from app.trash.routes import router as trash_router
from app.home.routes import router as home_router
from app.journal.routes import router as journal_router
from app.web import mount_web
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
app.include_router(stocks_router)
app.include_router(board_router)
app.include_router(updates_router)
app.include_router(credits_router)
app.include_router(account_router)
app.include_router(marketdata_router)
app.include_router(trash_router)
app.include_router(home_router)
app.include_router(journal_router)


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


# 웹 정적 빌드 서빙 (모든 API 라우트 뒤에 등록해야 한다). 빌드가 없으면 아무것도 하지 않는다.
mount_web(app)
