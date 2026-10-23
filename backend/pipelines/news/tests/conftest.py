"""DB 테스트 안전장치.

DB 테스트는 임베딩 테이블을 지우고 다시 만들고, 기사·종목 연결·수집 기록 테이블을 비운다.
그래서 TEST_DATABASE_URL이 실제 작업 DB(memos 등)를 가리키면 데이터가 사라진다.
DB 이름에 'test'가 없으면 테스트를 시작하지 않는다.
"""
import os

import pytest


def pytest_configure(config):
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        return
    try:
        from psycopg.conninfo import conninfo_to_dict
        name = conninfo_to_dict(dsn).get("dbname") or ""
    except Exception:
        name = ""
    if "test" not in name.lower():
        pytest.exit(
            f"TEST_DATABASE_URL의 DB 이름('{name}')에 'test'가 없습니다. 이 테스트는 테이블을 비우므로 "
            "버려도 되는 별도 테스트 DB에서만 실행하세요. 실제 작업 DB는 지정하지 마세요.",
            returncode=2)
