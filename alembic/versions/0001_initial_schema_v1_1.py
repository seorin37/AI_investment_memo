"""initial schema v1.1 (39 tables)"""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL_FILE = Path(__file__).resolve().parent.parent / "sql" / "0001_schema_v1_1.sql"


def upgrade() -> None:
    # 여러 문장이 든 SQL 파일이라 드라이버 연결로 한 번에 실행한다.
    # 같은 트랜잭션 안이라 중간에 실패하면 전부 롤백된다.
    raw = op.get_bind().connection.driver_connection
    raw.execute(SQL_FILE.read_text(encoding="utf-8"))

    # 두 컬럼(또는 세 컬럼) 중 정확히 하나만 값이 있어야 한다.
    op.execute(
        "ALTER TABLE tracking_matches ADD CONSTRAINT ck_tracking_matches_one_source "
        "CHECK (num_nonnulls(news_id, disclosure_rcept_no) = 1)"
    )
    op.execute(
        "ALTER TABLE update_sources ADD CONSTRAINT ck_update_sources_one_source "
        "CHECK (num_nonnulls(news_id, disclosure_rcept_no, price_event_id) = 1)"
    )


def downgrade() -> None:
    raise RuntimeError("초기 스키마는 되돌리지 않습니다. 개발 DB를 새로 만드세요.")
