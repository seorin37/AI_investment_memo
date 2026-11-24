"""Separate provider ratios from confirmed-close analysis ratios.

Revision ID: 0024_friday_fundamental_ratios
Revises: 0023_quiz_questions
Create Date: 2026-11-23
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0024_friday_fundamental_ratios"
down_revision: Union[str, Sequence[str], None] = "0023_quiz_questions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
ALTER TABLE stock_fundamentals_snapshot
  ADD COLUMN analysis_per numeric(18,6),
  ADD COLUMN analysis_pbr numeric(18,6),
  ADD CONSTRAINT ck_stock_fundamentals_snapshot_analysis_ratios
    CHECK (
      (analysis_per IS NULL OR analysis_per >= 0)
      AND (analysis_pbr IS NULL OR analysis_pbr >= 0)
    );

COMMENT ON COLUMN stock_fundamentals_snapshot.per IS
  'KIS inquire-price 제공 PER 원본. 음수 공급값은 기존 정책에 따라 NULL';
COMMENT ON COLUMN stock_fundamentals_snapshot.pbr IS
  'KIS inquire-price 제공 PBR 원본. 음수 공급값은 기존 정책에 따라 NULL';
COMMENT ON COLUMN stock_fundamentals_snapshot.analysis_per IS
  '확정 종가 / KIS 원본 EPS. EPS가 양수일 때만 계산';
COMMENT ON COLUMN stock_fundamentals_snapshot.analysis_pbr IS
  '확정 종가 / KIS 원본 BPS. BPS가 양수일 때만 계산';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE stock_fundamentals_snapshot
          DROP CONSTRAINT IF EXISTS ck_stock_fundamentals_snapshot_analysis_ratios,
          DROP COLUMN IF EXISTS analysis_per,
          DROP COLUMN IF EXISTS analysis_pbr
        """
    )
