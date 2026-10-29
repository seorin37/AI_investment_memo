"""KIS prices, adjusted volume, and fundamentals snapshots.

Revision ID: 0011_kis_market_data
Revises: 0010_adjusted_prices_daily
Create Date: 2026-10-28
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0011_kis_market_data"
down_revision: Union[str, Sequence[str], None] = "0010_adjusted_prices_daily"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
ALTER TABLE prices_daily
  ADD COLUMN source text,
  ADD COLUMN market_metadata_source text;

UPDATE prices_daily
SET source = 'KRX_OPEN_API',
    market_metadata_source = CASE
      WHEN market_cap IS NOT NULL OR listed_shares IS NOT NULL
      THEN 'KRX_OPEN_API'
      ELSE NULL
    END;

ALTER TABLE prices_daily
  ALTER COLUMN source SET NOT NULL,
  ADD CONSTRAINT ck_prices_daily_source
    CHECK (source IN ('KRX_OPEN_API', 'KIS')),
  ADD CONSTRAINT ck_prices_daily_market_metadata_source
    CHECK (
      market_metadata_source IS NULL
      OR market_metadata_source IN ('KRX_OPEN_API', 'KIS')
    );

COMMENT ON TABLE prices_daily IS
  '개별 종목 확정 일봉. 신규 OHLCV/거래대금 공급원은 KIS이며 기존 KRX 행은 source로 구분';
COMMENT ON COLUMN prices_daily.source IS
  'OHLCV와 거래대금 공급원. 기존 KRX_OPEN_API 또는 신규 KIS';
COMMENT ON COLUMN prices_daily.market_metadata_source IS
  '해당 행 market_cap/listed_shares 공급원. KIS 기간시세가 과거값을 제공하지 않으면 NULL';

ALTER TABLE adjusted_prices_daily
  ADD COLUMN volume bigint;

ALTER TABLE adjusted_prices_daily
  DROP CONSTRAINT ck_adjusted_prices_daily_source,
  ADD CONSTRAINT ck_adjusted_prices_daily_source
    CHECK (source IN ('PYKRX_NAVER', 'KIS')),
  ADD CONSTRAINT ck_adjusted_prices_daily_volume
    CHECK (volume IS NULL OR volume >= 0);

COMMENT ON TABLE adjusted_prices_daily IS
  '소급 수정 일별 OHLCV. 기존 PYKRX_NAVER 행과 신규 KIS 행을 source로 구분';
COMMENT ON COLUMN adjusted_prices_daily.volume IS
  '수정 기준 거래량. 기존 pykrx 이행 행은 NULL, KIS 신규 행은 API 값 저장';
COMMENT ON COLUMN adjusted_prices_daily.adjustment_basis IS
  '수정주가 호출 정책. KIS는 FID_ORG_ADJ_PRC=0';

CREATE TABLE stock_fundamentals_snapshot (
  symbol              char(6)       NOT NULL REFERENCES stocks(symbol),
  basis_trade_date    date          NOT NULL,
  per                 numeric(18,6),
  pbr                 numeric(18,6),
  eps                 numeric(20,4),
  bps                 numeric(20,4),
  w52_high             numeric(14,2),
  w52_high_date        date,
  w52_low              numeric(14,2),
  w52_low_date         date,
  market_cap           numeric(24,0),
  listed_shares        bigint,
  reference_price      numeric(14,2),
  final_close          numeric(14,2) NOT NULL,
  source               text          NOT NULL,
  collected_at         timestamptz   NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol, basis_trade_date),
  CONSTRAINT ck_stock_fundamentals_snapshot_ratios
    CHECK ((per IS NULL OR per >= 0) AND (pbr IS NULL OR pbr >= 0)),
  CONSTRAINT ck_stock_fundamentals_snapshot_w52_prices
    CHECK (
      (w52_high IS NULL OR w52_high > 0)
      AND (w52_low IS NULL OR w52_low > 0)
      AND (w52_high IS NULL OR w52_low IS NULL OR w52_high >= w52_low)
    ),
  CONSTRAINT ck_stock_fundamentals_snapshot_w52_pairs
    CHECK (
      (w52_high IS NULL) = (w52_high_date IS NULL)
      AND (w52_low IS NULL) = (w52_low_date IS NULL)
    ),
  CONSTRAINT ck_stock_fundamentals_snapshot_counts
    CHECK (
      (market_cap IS NULL OR market_cap >= 0)
      AND (listed_shares IS NULL OR listed_shares > 0)
    ),
  CONSTRAINT ck_stock_fundamentals_snapshot_prices
    CHECK (reference_price IS NULL OR reference_price > 0),
  CONSTRAINT ck_stock_fundamentals_snapshot_final_close
    CHECK (final_close > 0),
  CONSTRAINT ck_stock_fundamentals_snapshot_source
    CHECK (source = 'KIS')
);

CREATE INDEX stock_fundamentals_snapshot_basis_date_idx
  ON stock_fundamentals_snapshot (basis_trade_date);

COMMENT ON TABLE stock_fundamentals_snapshot IS
  'KIS 현재가 API 투자지표와 52주/현재 시가총액 스냅샷. 서비스 가격은 final_close 사용';
COMMENT ON COLUMN stock_fundamentals_snapshot.reference_price IS
  'KIS 현재가 API stck_prpr. 수집 시점 값이므로 실시간 서비스 가격으로 사용하지 않음';
COMMENT ON COLUMN stock_fundamentals_snapshot.final_close IS
  '동일 수집에서 확인한 최신 확정 KIS 일봉 종가';
COMMENT ON COLUMN stock_fundamentals_snapshot.per IS
  'KIS 제공값 원형. NULL은 미제공, 0은 공급자가 반환한 0, EPS/BPS는 음수 허용';
"""


DOWNGRADE_SQL = """
DROP TABLE IF EXISTS stock_fundamentals_snapshot;

ALTER TABLE adjusted_prices_daily
  DROP CONSTRAINT IF EXISTS ck_adjusted_prices_daily_volume,
  DROP CONSTRAINT IF EXISTS ck_adjusted_prices_daily_source,
  DROP COLUMN IF EXISTS volume,
  ADD CONSTRAINT ck_adjusted_prices_daily_source
    CHECK (source = 'PYKRX_NAVER');

ALTER TABLE prices_daily
  DROP CONSTRAINT IF EXISTS ck_prices_daily_market_metadata_source,
  DROP CONSTRAINT IF EXISTS ck_prices_daily_source,
  DROP COLUMN IF EXISTS market_metadata_source,
  DROP COLUMN IF EXISTS source;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
