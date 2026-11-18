"""계산 지표 테이블 (financial_metrics)

Revision ID: 0017_financial_metrics
Revises: 0016_financials_quarterly
Create Date: 2026-11-16

- 기업정보 페이지 지표(영업이익률·순이익률·ROE·부채비율·유동비율·당좌비율·이자보상배율·유보율)와
  금융사 영업수익 대용값을 계산해 저장한다(2026-11-16 결정: 화면 표시 여부와 상관없이 모두 계산·적재).
  docs/company-page-data-gaps-plan.md
- 한 행 = financials 한 행 (symbol, period_end). 원본(financials·financials_fin·0016 분기 테이블)은 건드리지 않는다.
- interest_cost는 재무 적재 때 원천 응답에서 고른 이자비용(누적값)이다. 우선순위:
  손익계산서 이자비용(income_statement) → 현금흐름표 조정 '이자비용'(cf_adjustment) → 현금흐름표 '이자의 지급'(cf_paid).
- 비율은 적재 코드가 원본을 쓸 때마다 그 회사 전체를 다시 계산한다(financial_metrics.recompute_symbol).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0017_financial_metrics"
down_revision: Union[str, Sequence[str], None] = "0016_financials_quarterly"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
CREATE TABLE financial_metrics (
  symbol                   char(6)        NOT NULL REFERENCES stocks(symbol) DEFERRABLE INITIALLY IMMEDIATE,
  period_end               date           NOT NULL,
  period_type              report_period  NOT NULL,
  fiscal_year_end          date           NOT NULL,
  fs_div                   text,
  interest_cost            numeric(20,0),
  interest_cost_basis      text           CHECK (interest_cost_basis IN ('income_statement', 'cf_adjustment', 'cf_paid')),
  operating_margin         numeric(14,2),
  net_margin               numeric(14,2),
  roe                      numeric(14,2),
  debt_ratio               numeric(14,2),
  current_ratio            numeric(14,2),
  quick_ratio              numeric(14,2),
  interest_coverage        numeric(14,2),
  interest_coverage_basis  text           CHECK (interest_coverage_basis IN ('income_statement', 'cf_adjustment', 'cf_paid')),
  reserve_ratio            numeric(14,2),
  fin_operating_revenue    numeric(20,0),
  fin_revenue_basis        text           CHECK (fin_revenue_basis IN ('revenue', 'securities_operating_revenue', 'insurance_revenue', 'nii_plus_fee')),
  null_reasons             jsonb          NOT NULL DEFAULT '{}'::jsonb,
  computed_at              timestamptz    NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol, period_end)
);

COMMENT ON TABLE financial_metrics IS '기업정보 페이지 계산 지표. 원본은 financials·financials_fin·financials_quarterly·financials_fin_quarterly';
COMMENT ON COLUMN financial_metrics.interest_cost IS '이자비용 누적값(원). 근거는 interest_cost_basis. cf_paid는 현금 이자지급(근사)';
COMMENT ON COLUMN financial_metrics.operating_margin IS '분기 단독 영업이익 / 분기 단독 매출 x100 (매출이 없는 금융사는 fin_operating_revenue)';
COMMENT ON COLUMN financial_metrics.net_margin IS '분기 단독 지배주주 순이익 / 분기 단독 매출 x100 (매출이 없는 금융사는 fin_operating_revenue)';
COMMENT ON COLUMN financial_metrics.roe IS '최근 4분기(TTM) 지배주주 순이익 / 기말 자본총계 x100';
COMMENT ON COLUMN financial_metrics.debt_ratio IS '부채총계 / 자본총계 x100 (기말)';
COMMENT ON COLUMN financial_metrics.current_ratio IS '유동자산 / 유동부채 x100 (기말)';
COMMENT ON COLUMN financial_metrics.quick_ratio IS '(유동자산 - 재고자산) / 유동부채 x100 (기말)';
COMMENT ON COLUMN financial_metrics.interest_coverage IS 'TTM 영업이익 / TTM 이자비용 (배)';
COMMENT ON COLUMN financial_metrics.reserve_ratio IS '(자본잉여금 + 이익잉여금) / 자본금 x100 (기말)';
COMMENT ON COLUMN financial_metrics.fin_operating_revenue IS '금융사 분기 단독 영업수익 대용값. 근거는 fin_revenue_basis';
COMMENT ON COLUMN financial_metrics.null_reasons IS 'NULL 컬럼별 사유 {컬럼: 코드}';
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS financial_metrics;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
