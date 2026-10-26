"""환경 연결 확인용 최소 백엔드. 실제 API는 feature/be-* 브랜치에서 추가한다."""

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from pipelines.common.db import DatabaseConfigError, get_read_dsn

load_dotenv()

app = FastAPI(title="Memos API")


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
