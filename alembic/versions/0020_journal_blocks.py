"""투자 기록 블록 원본 (journal_entries.blocks)

Revision ID: 0020_journal_blocks
Revises: 0019_ai_outputs_and_credits
Create Date: 2026-11-20

- 앱 에디터의 블록(문단·제목·체크·표·첨부, 블록 id·강조 포함)을 그대로 담는 jsonb 칸. 이게 원본이다.
- body(text, Markdown)는 저장할 때 blocks 로 만들어 넣는다 (검색·LLM용). 기존 'Markdown 본문' 결정은 그대로.
- 칸 추가만 한다. 기존 행은 건드리지 않는다 (NULL 이면 API 가 body 를 문단 하나로 보여 준다).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0020_journal_blocks"
down_revision: Union[str, Sequence[str], None] = "0019_ai_outputs_and_credits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
ALTER TABLE journal_entries ADD COLUMN blocks jsonb;
COMMENT ON COLUMN journal_entries.blocks IS
  '앱 에디터 블록 원본 [{id, type: paragraph|heading|checklist|table|attachment, ...}]. body(Markdown)는 저장할 때 이 값으로 만든다';
"""

DOWNGRADE_SQL = """
ALTER TABLE journal_entries DROP COLUMN blocks;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
