"""크레딧을 다 쓴 채 갱신일이 지나 자동으로 꺼진 AI 연결 메모 표시 (memos.ai_auto_off_at)

Revision ID: 0026_memos_ai_auto_off
Revises: 0025_studio_items_deleted_at
Create Date: 2026-11-24

- 서린 님 결정 (2026-11-24): 크레딧이 0이 되면 '충전하거나 플랜을 업그레이드하지 않으면 AI 연결이 모두 꺼져요' 선택 창.
  고르지 않은 채 사용자별 갱신일이 지나면 서버가 AI 연결 메모를 모두 끄고(app/credits/ledger.refresh), 이 칸에 끈 시각을 적는다.
- 화면은 이 칸으로 '지난 기간 AI 사용량을 다 써서 AI 연결 메모 N개가 꺼졌어요' 안내를 한 번 띄운다. 확인하거나 그 메모를 다시 켜면 NULL.
- 사용자가 직접 끈 메모(선택 창 '모두 끄기' 포함)는 적지 않는다.
- 기존 표와 데이터는 바꾸지 않는다 (칸 추가만, 기본값 NULL).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0026_memos_ai_auto_off"
down_revision: Union[str, Sequence[str], None] = "0025_studio_items_deleted_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
ALTER TABLE memos ADD COLUMN ai_auto_off_at timestamptz;
CREATE INDEX ix_memos_ai_auto_off ON memos (user_id) WHERE ai_auto_off_at IS NOT NULL;
COMMENT ON COLUMN memos.ai_auto_off_at IS '크레딧을 다 쓴 채 갱신일이 지나 서버가 AI 연결을 끈 시각 (NULL = 아님). 안내를 확인하거나 다시 켜면 NULL';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memos_ai_auto_off")
    op.execute("ALTER TABLE memos DROP COLUMN ai_auto_off_at")
