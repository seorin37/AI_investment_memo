"""사이드바 내 종목 순서 (user_stocks.position)

Revision ID: 0021_user_stocks_position
Revises: 0020_journal_blocks
Create Date: 2026-11-20

- 웹 사이드바에서 끌어 옮긴 내 종목 순서를 서버에 저장한다 (지금은 웹이 자기 상태 묶음에만 저장).
- 한 사용자의 지우지 않은 종목마다 0부터. 기존 행은 지금 화면 순서(추가한 순서 → 종목코드)로 채운다 → 적용 전후 화면 순서가 같다.
- 지운 종목(deleted_at)은 NULL로 두고, 다시 추가하면 맨 뒤 번호를 받는다.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0021_user_stocks_position"
down_revision: Union[str, Sequence[str], None] = "0020_journal_blocks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
ALTER TABLE user_stocks ADD COLUMN position integer CHECK (position IS NULL OR position >= 0);
UPDATE user_stocks us SET position = o.rn
FROM (SELECT user_id, symbol, (row_number() OVER (PARTITION BY user_id ORDER BY created_at, symbol) - 1)::integer AS rn
      FROM user_stocks WHERE deleted_at IS NULL) o
WHERE us.user_id = o.user_id AND us.symbol = o.symbol;
CREATE INDEX ix_user_stocks_user_position ON user_stocks (user_id, position);
COMMENT ON COLUMN user_stocks.position IS '사이드바 내 종목 순서 (0부터, 사용자별). NULL이면 추가한 순서로 맨 뒤';
"""

DOWNGRADE_SQL = """
DROP INDEX ix_user_stocks_user_position;
ALTER TABLE user_stocks DROP COLUMN position;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
