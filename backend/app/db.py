"""DB 연결. 수집 코드와 API는 모두 여기서 가져다 쓴다.

사용법 (수집 코드):
    from app.db import get_session
    from sqlalchemy import text

    with get_session() as s:
        s.execute(text("SELECT count(*) FROM stocks"))
"""
import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 프로젝트 루트의 .env를 읽는다 (backend/app/db.py 기준 두 단계 위)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

def write_database_url(environ=None) -> str:
    env = os.environ if environ is None else environ
    url = env.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL이 없습니다. 환경변수나 .env를 확인하세요.")
    return url.strip()


def read_database_url(environ=None) -> str:
    env = os.environ if environ is None else environ
    url = env.get("READONLY_DATABASE_URL") or env.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "READONLY_DATABASE_URL 또는 DATABASE_URL이 없습니다. 환경변수나 .env를 확인하세요."
        )
    return url.strip()


_write_url = write_database_url()
_read_url = read_database_url()
engine = create_engine(_write_url, pool_pre_ping=True)
read_engine = engine if _read_url == _write_url else create_engine(_read_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
ReadSessionLocal = sessionmaker(bind=read_engine, expire_on_commit=False)


@contextmanager
def get_session():
    """성공하면 commit, 에러가 나면 rollback 후 다시 던진다."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """FastAPI 의존성용."""
    with get_session() as session:
        yield session


@contextmanager
def get_read_session():
    """조회 전용 세션. 성공 경로에서도 commit하지 않는다."""
    session = ReadSessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_read_db():
    """FastAPI 조회 전용 의존성."""
    with get_read_session() as session:
        yield session
