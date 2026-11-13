"""분기 단독 손익 테이블 (financials_quarterly · financials_fin_quarterly)

Revision ID: 0016_financials_quarterly
Revises: 0015_news_article_bodies
Create Date: 2026-11-13

- financials·financials_fin의 손익 항목은 DART 보고서 그대로 회계연도 누적값이다(q1 3개월, half 6개월, q3 9개월,
  annual 12개월). 누적 원본은 그대로 두고, 분기 단독값을 이 테이블에 따로 저장한다(2026-11-13 팀 결정).
- Q1은 q1 보고값을 그대로, Q2=half−q1, Q3=q3−half, Q4=annual−q3. 같은 회계연도(결산월 기준) 안에서만 뺀다.
- 값을 못 구하면 NULL과 null_reasons(missing_prev_period·source_null·fs_div_mismatch·needs_review)를 남긴다.
- 재무상태표 항목(자산·부채·자본·대출·예수금)과 EPS는 대상이 아니다. EPS는 기간마다 주식 수가 달라 누적 차이가 분기 EPS가 아니다.
- 적재 코드(financials_loader.upsert_*)가 원본 한 기간을 쓸 때마다 그 회사·그 회계연도를 다시 계산한다.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0016_financials_quarterly"
down_revision: Union[str, Sequence[str], None] = "0015_news_article_bodies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
CREATE TABLE financials_quarterly (
  symbol            char(6)        NOT NULL REFERENCES stocks(symbol) DEFERRABLE INITIALLY IMMEDIATE,
  period_end        date           NOT NULL,
  fiscal_year_end   date           NOT NULL,
  quarter           smallint       NOT NULL CHECK (quarter BETWEEN 1 AND 4),
  fs_div            text,
  revenue           numeric(20,0),
  operating_income  numeric(20,0),
  net_income        numeric(20,0),
  method            text           NOT NULL CHECK (method IN ('reported', 'derived')),
  null_reasons      jsonb          NOT NULL DEFAULT '{}'::jsonb,
  computed_at       timestamptz    NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol, period_end)
);
CREATE INDEX ix_financials_quarterly_fy ON financials_quarterly (symbol, fiscal_year_end);

CREATE TABLE financials_fin_quarterly (
  symbol                        char(6)        NOT NULL REFERENCES stocks(symbol) DEFERRABLE INITIALLY IMMEDIATE,
  period_end                    date           NOT NULL,
  fiscal_year_end               date           NOT NULL,
  quarter                       smallint       NOT NULL CHECK (quarter BETWEEN 1 AND 4),
  fs_div                        text,
  net_interest_income           numeric(20,0),
  fee_income                    numeric(20,0),
  loan_loss_provision           numeric(20,0),
  insurance_revenue             numeric(20,0),
  securities_operating_revenue  numeric(20,0),
  method                        text           NOT NULL CHECK (method IN ('reported', 'derived')),
  null_reasons                  jsonb          NOT NULL DEFAULT '{}'::jsonb,
  computed_at                   timestamptz    NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol, period_end)
);
CREATE INDEX ix_financials_fin_quarterly_fy ON financials_fin_quarterly (symbol, fiscal_year_end);

COMMENT ON TABLE financials_quarterly IS '분기 단독 손익. financials 누적값의 같은 회계연도 차이(Q1=q1, Q2=half-q1, Q3=q3-half, Q4=annual-q3). 원본은 financials';
COMMENT ON TABLE financials_fin_quarterly IS '금융사 분기 단독 손익. financials_fin 누적값의 차이. 비율(BIS 등)·잔액(대출·예수금)은 대상 아님';
COMMENT ON COLUMN financials_quarterly.fiscal_year_end IS '결산월 기준 회계연도 말 (12월 결산이 아니면 달력 연도와 다름)';
COMMENT ON COLUMN financials_quarterly.method IS 'reported: Q1 보고값 그대로 / derived: 누적값 차이';
COMMENT ON COLUMN financials_quarterly.null_reasons IS 'NULL 컬럼별 사유 {컬럼: missing_prev_period|source_null|fs_div_mismatch|needs_review}';
COMMENT ON COLUMN financials_fin_quarterly.null_reasons IS 'NULL 컬럼별 사유 {컬럼: missing_prev_period|source_null|fs_div_mismatch|needs_review}';
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS financials_fin_quarterly;
DROP TABLE IF EXISTS financials_quarterly;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
