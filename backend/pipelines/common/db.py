"""파이프라인 공통 DB 유틸리티.

공시팀: SQLAlchemy 엔진
뉴스팀: psycopg DSN 및 ingest_runs 실행 기록
"""

from __future__ import annotations

import os
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


class DatabaseConfigError(RuntimeError):
    pass


def load_env() -> None:
    """프로젝트 루트 .env를 읽되 기존 환경변수는 유지한다."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def _environment(environ=None):
    if environ is None:
        load_env()
        return os.environ
    return environ


def database_url(environ=None) -> str:
    """Return the read/write application URL without exposing it in errors."""
    env = _environment(environ)
    url = env.get("DATABASE_URL")
    if not url:
        raise DatabaseConfigError(
            "DATABASE_URL이 없습니다. 환경변수나 .env를 확인하세요."
        )
    return url.strip()


def read_database_url(environ=None) -> str:
    """Return the read-only URL, falling back to the legacy application URL."""
    env = _environment(environ)
    url = env.get("READONLY_DATABASE_URL") or env.get("DATABASE_URL")
    if not url:
        raise DatabaseConfigError(
            "READONLY_DATABASE_URL 또는 DATABASE_URL이 없습니다. 환경변수나 .env를 확인하세요."
        )
    return url.strip()


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_read_engine() -> Engine:
    return create_engine(read_database_url(), pool_pre_ping=True)


def _psycopg_url(url: str) -> str:
    """Remove a SQLAlchemy driver suffix while preserving an encoded URL."""
    return re.sub(
        r"^(postgres(?:ql)?)\+\w+://",
        r"\1://",
        url.strip(),
    )


def get_dsn(environ=None) -> str | None:
    """Return the read/write psycopg connection string."""
    env = _environment(environ)
    url = env.get("DATABASE_URL")

    if url:
        return _psycopg_url(url)

    if not env.get("POSTGRES_USER") or not env.get("POSTGRES_DB"):
        return None

    from psycopg.conninfo import make_conninfo

    return make_conninfo(
        host=env.get("POSTGRES_HOST", "localhost"),
        port=env.get("POSTGRES_PORT", "5432"),
        user=env["POSTGRES_USER"],
        password=env.get("POSTGRES_PASSWORD", ""),
        dbname=env["POSTGRES_DB"],
    )


def get_read_dsn(environ=None) -> str | None:
    """Return a read-only psycopg connection string with legacy fallback."""
    env = _environment(environ)
    url = env.get("READONLY_DATABASE_URL")
    if url:
        return _psycopg_url(url)
    return get_dsn(env)


def start_run(cur, job: str, target_date: date | None) -> int:
    cur.execute(
        "INSERT INTO ingest_runs (job, target_date) "
        "VALUES (%s::ingest_job, %s) RETURNING id",
        (job, target_date),
    )
    return cur.fetchone()[0]


def finish_run(
    cur,
    run_id: int,
    fetched: int,
    error: str | None = None,
) -> None:
    status = "failed" if error else ("empty" if fetched == 0 else "success")

    cur.execute(
        """
        UPDATE ingest_runs
        SET finished_at = now(),
            status = %s::ingest_status,
            fetched_count = %s,
            error = %s
        WHERE id = %s
        """,
        (status, fetched, error, run_id),
    )
