"""pykrx 수정주가 일별 테이블

Revision ID: 0010_adjusted_prices_daily
Revises: 0009_news_clusters
Create Date: 2026-10-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0010_adjusted_prices_daily"
down_revision: Union[str, Sequence[str], None] = "0009_news_clusters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
CREATE TABLE adjusted_prices_daily (
  symbol            char(6)      NOT NULL REFERENCES stocks(symbol),
  trade_date        date         NOT NULL,
  open              numeric(14,2) NOT NULL,
  high              numeric(14,2) NOT NULL,
  low               numeric(14,2) NOT NULL,
  close             numeric(14,2) NOT NULL,
  source            text         NOT NULL,
  adjustment_basis  text         NOT NULL,
  collected_at      timestamptz  NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol, trade_date),
  CONSTRAINT ck_adjusted_prices_daily_source
    CHECK (source = 'PYKRX_NAVER'),
  CONSTRAINT ck_adjusted_prices_daily_positive_ohlc
    CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0),
  CONSTRAINT ck_adjusted_prices_daily_ohlc_order
    CHECK (high >= GREATEST(open, close) AND low <= LEAST(open, close) AND high >= low)
);

CREATE INDEX adjusted_prices_daily_trade_date_idx
  ON adjusted_prices_daily (trade_date);

COMMENT ON TABLE adjusted_prices_daily IS
  'pykrx가 제공하는 소급 수정 일별 OHLC. KRX 원시 시세 prices_daily와 분리 보관';
COMMENT ON COLUMN adjusted_prices_daily.source IS
  '수집 경로. 현재 PYKRX_NAVER만 허용';
COMMENT ON COLUMN adjusted_prices_daily.adjustment_basis IS
  '수정주가 산출 정책/호출 방식 식별자';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS adjusted_prices_daily")
