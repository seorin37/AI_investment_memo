"""스튜디오 만든 항목도 휴지통으로 (studio_items.deleted_at)

Revision ID: 0025_studio_items_deleted_at
Revises: 0024_friday_fundamental_ratios
Create Date: 2026-11-24

- 팀장 결정 (2026-11-24): 스튜디오 만든 항목(주간보고서·AI 오디오·투자 실험실)도 지우면 바로 없애지 않고 휴지통으로 보낸다.
- 메모(memos.deleted_at)·투자 기록(journal_entries.deleted_at)과 같은 방식: 지운 시각을 적고, 휴지통에서 복원하면 비운다.
- 30일 보관(expires_at)은 그대로 흐른다. 만료되면 목록에서도 휴지통에서도 보이지 않는다.
- 기존 표와 데이터는 바꾸지 않는다 (칸 추가만, 기본값 NULL = 지우지 않음).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0025_studio_items_deleted_at"
down_revision: Union[str, Sequence[str], None] = "0024_friday_fundamental_ratios"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
ALTER TABLE studio_items ADD COLUMN deleted_at timestamptz;
CREATE INDEX ix_studio_items_trash ON studio_items (user_id, deleted_at) WHERE deleted_at IS NOT NULL;
COMMENT ON COLUMN studio_items.deleted_at IS '휴지통으로 보낸 시각 (NULL = 지우지 않음). 복원하면 NULL';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_studio_items_trash")
    op.execute("ALTER TABLE studio_items DROP COLUMN deleted_at")
