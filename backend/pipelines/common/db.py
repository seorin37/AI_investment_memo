"""파이프라인 공통 DB 유틸: .env 읽기, 접속 문자열, 실행 기록(ingest_runs).

뉴스 파트에서 먼저 만들었다. 이미 팀의 common/db.py가 있으면 같은 이름의 함수끼리 합칠 것.
"""

from __future__ import annotations

import re
from datetime import date


def start_run(cur, job: str, target_date: date | None) -> int:
    cur.execute("INSERT INTO ingest_runs (job, target_date) VALUES (%s::ingest_job, %s) RETURNING id",
                (job, target_date))
    return cur.fetchone()[0]


def finish_run(cur, run_id: int, fetched: int, error: str | None = None) -> None:
    status = "failed" if error else ("empty" if fetched == 0 else "success")
    cur.execute("""UPDATE ingest_runs SET finished_at = now(), status = %s::ingest_status,
                   fetched_count = %s, error = %s WHERE id = %s""",
                (status, fetched, error, run_id))


def load_env() -> None:
    """같은 폴더 또는 상위의 .env를 읽는다. 이미 설정된 환경변수는 덮어쓰지 않는다."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def get_dsn(environ=None) -> str | None:
    """psycopg용 접속 문자열을 돌려준다.

    - DATABASE_URL이 있으면 SQLAlchemy 형식(postgresql+psycopg://)의 '+드라이버'를 떼어 쓴다.
    - 없으면 POSTGRES_HOST/PORT/USER/PASSWORD/DB 로 조립한다(비밀번호의 특수문자도 안전).
    """
    import os
    env = os.environ if environ is None else environ
    url = env.get("DATABASE_URL")
    if url:
        return re.sub(r"^(postgres(?:ql)?)\+\w+://", r"\1://", url.strip())
    if not env.get("POSTGRES_USER") or not env.get("POSTGRES_DB"):
        return None
    from psycopg.conninfo import make_conninfo
    return make_conninfo(
        host=env.get("POSTGRES_HOST", "localhost"), port=env.get("POSTGRES_PORT", "5432"),
        user=env["POSTGRES_USER"], password=env.get("POSTGRES_PASSWORD", ""), dbname=env["POSTGRES_DB"])