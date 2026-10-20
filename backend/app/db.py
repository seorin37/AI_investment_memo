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

_url = os.environ.get("DATABASE_URL")
if not _url:
    raise RuntimeError("DATABASE_URL이 없습니다. .env를 확인하세요.")

engine = create_engine(_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


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
