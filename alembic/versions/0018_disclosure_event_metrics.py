"""사건 공시 표준 비율 테이블 (disclosure_event_metrics)

Revision ID: 0018_disclosure_event_metrics
Revises: 0017_financial_metrics
Create Date: 2026-11-17

- 수시공시 정리값(disclosure_events.fields)의 금액·주식 수를 회사 규모와 견준 비율을 미리 계산해 둔다.
  "유상증자 규모가 영업이익의 몇 배야?", "자사주를 얼마나 사?", "배당성향은?" 같은 질문·카드·화면에 쓴다.
- 한 행 = 사건 공시 하나 (rcept_no). 사건 종류마다 비율이 달라 metrics는 jsonb {지표: 값}.
  inputs에 계산에 쓴 분모(직전 연도 영업이익·자본총계·시가총액 등)와 그 기준 날짜를 남긴다 (출처를 보여 줄 수 있게).
- 분모는 공시 접수일 '전'의 값만 쓴다 (재무는 기간 끝이 접수일 전인 최신 행, 시가총액은 접수일 전 최근 거래일).
- 자회사 공시(is_subsidiary)는 모회사 숫자와 견주면 오해를 부르므로 계산하지 않고 null_reasons에 사유를 남긴다.
- 원본(disclosure_events·financials·prices_daily)은 건드리지 않는다. 계산: pipelines/disclosures/event_metrics.py
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0018_disclosure_event_metrics"
down_revision: Union[str, Sequence[str], None] = "0017_financial_metrics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
CREATE TABLE disclosure_event_metrics (
  rcept_no      text         PRIMARY KEY REFERENCES disclosures(rcept_no) ON DELETE CASCADE,
  symbol        char(6)      NOT NULL,
  event_type    text         NOT NULL,
  base_date     date         NOT NULL,
  metrics       jsonb        NOT NULL DEFAULT '{}'::jsonb,
  inputs        jsonb        NOT NULL DEFAULT '{}'::jsonb,
  null_reasons  jsonb        NOT NULL DEFAULT '{}'::jsonb,
  calc_version  text         NOT NULL,
  computed_at   timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX disclosure_event_metrics_symbol_idx ON disclosure_event_metrics (symbol, base_date DESC);

COMMENT ON TABLE disclosure_event_metrics IS '사건 공시 표준 비율. 원본은 disclosure_events.fields + financials + prices_daily';
COMMENT ON COLUMN disclosure_event_metrics.base_date IS '공시 접수일. 분모는 이 날짜 전의 값만 쓴다';
COMMENT ON COLUMN disclosure_event_metrics.metrics IS '{지표: 값}. 비율은 %(_pct) 또는 배(_x), 금액은 원(_krw)';
COMMENT ON COLUMN disclosure_event_metrics.inputs IS '계산에 쓴 분모와 기준 {이름: {value, period_end|trade_date, source}}';
COMMENT ON COLUMN disclosure_event_metrics.null_reasons IS '계산하지 못한 지표별 사유 {지표: 코드}';
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS disclosure_event_metrics;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
