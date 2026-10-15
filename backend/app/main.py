"""환경 연결 확인용 최소 백엔드. 실제 API는 feature/be-* 브랜치에서 추가한다."""

import os

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

load_dotenv()

app = FastAPI(title="Memos API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    try:
        with psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            dbname=os.getenv("POSTGRES_DB"),
            connect_timeout=3,
        ) as conn:
            row = conn.execute(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
        return {"status": "ok", "pgvector": row is not None}
    except Exception as e:
        return JSONResponse(
            status_code=503, content={"status": "error", "detail": str(e)}
        )
