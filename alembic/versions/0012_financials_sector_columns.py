"""Financial-sector columns, NULL reasons, and stocks.fin_type.

Revision ID: 0012_financials_sector_columns
Revises: 0011_kis_market_data
Create Date: 2026-10-29
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0012_financials_sector_columns"
down_revision: Union[str, Sequence[str], None] = "0011_kis_market_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
ALTER TABLE financials_fin RENAME COLUMN solvency_ratio TO bis_ratio;

ALTER TABLE financials_fin
  ADD COLUMN loans numeric(20,0),
  ADD COLUMN deposits numeric(20,0),
  ADD COLUMN insurance_revenue numeric(20,0),
  ADD COLUMN securities_operating_revenue numeric(20,0),
  ADD COLUMN kics_ratio numeric(8,2),
  ADD COLUMN ncr_ratio numeric(8,2),
  ADD COLUMN null_reasons jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE financials
  ADD COLUMN null_reasons jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE stocks
  ADD COLUMN fin_type text,
  ADD CONSTRAINT ck_stocks_fin_type
    CHECK (fin_type IS NULL OR fin_type IN ('bank', 'insurance', 'securities', 'holding', 'other')),
  ADD CONSTRAINT ck_stocks_fin_type_sector
    CHECK (fin_type IS NULL OR sector = 'financial');

COMMENT ON COLUMN financials_fin.bis_ratio IS '은행·금융지주 BIS 총자본비율(%). 공시 본문에서 추출';
COMMENT ON COLUMN financials_fin.loans IS '상각후원가 측정 대출채권 (dart_LoansAtAmortisedCost)';
COMMENT ON COLUMN financials_fin.deposits IS '예수부채 (ifrs-full_DepositsFromCustomers)';
COMMENT ON COLUMN financials_fin.insurance_revenue IS 'IFRS17 보험수익, 재보험수익 제외 (ifrs-full_InsuranceRevenue)';
COMMENT ON COLUMN financials_fin.securities_operating_revenue IS '증권사 영업수익 (ifrs-full_Revenue). 증권사 financials.revenue는 NULL';
COMMENT ON COLUMN financials_fin.kics_ratio IS '보험 K-ICS 비율(%). 공시 본문에서 추출';
COMMENT ON COLUMN financials_fin.ncr_ratio IS '증권 순자본비율 NCR(%). 공시 본문에서 추출';
COMMENT ON COLUMN financials_fin.null_reasons IS 'NULL 컬럼별 사유 코드 {컬럼: not_applicable|no_standard_id|not_reported|needs_review|extract_failed}';
COMMENT ON COLUMN financials.null_reasons IS 'NULL 컬럼별 사유 코드 {컬럼: not_applicable|no_standard_id|not_reported|needs_review}';
COMMENT ON COLUMN stocks.fin_type IS '금융 세부 업종 bank|insurance|securities|holding|other. 일반 기업은 NULL';
"""

DOWNGRADE_SQL = """
ALTER TABLE stocks
  DROP CONSTRAINT ck_stocks_fin_type_sector,
  DROP CONSTRAINT ck_stocks_fin_type,
  DROP COLUMN fin_type;

ALTER TABLE financials DROP COLUMN null_reasons;

ALTER TABLE financials_fin
  DROP COLUMN null_reasons,
  DROP COLUMN ncr_ratio,
  DROP COLUMN kics_ratio,
  DROP COLUMN securities_operating_revenue,
  DROP COLUMN insurance_revenue,
  DROP COLUMN deposits,
  DROP COLUMN loans;

ALTER TABLE financials_fin RENAME COLUMN bis_ratio TO solvency_ratio;
COMMENT ON COLUMN financials_fin.solvency_ratio IS '은행 BIS / 보험 RBC 등';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
