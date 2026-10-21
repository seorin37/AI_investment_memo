"""ingest_job에 macro 추가, market_indices 값 자리수 확대, 토스증권 설명을 KRX 기준으로 수정"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 새 enum 값 추가는 트랜잭션 밖에서 실행한다.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE ingest_job ADD VALUE IF NOT EXISTS 'macro'")

    # 국채 금리처럼 소수 셋째 자리 이상이 필요한 지표를 위해 자리수를 넓힌다.
    op.execute('ALTER TABLE market_indices ALTER COLUMN "close" TYPE numeric(14,4)')

    op.execute(
        "COMMENT ON TABLE market_indices IS "
        "'지수·환율·금리 시계열 (ECOS, KRX 지수). code는 지표 이름, close는 그 날짜의 값'"
    )
    op.execute(
        "COMMENT ON TABLE prices_daily IS "
        "'KRX 일별매매정보 기반 일봉 OHLCV, 영업일 약 260일(1년). "
        "이동평균선(5/20/60/120일)은 이 표로 코드에서 계산하며 저장하지 않는다'"
    )
    op.execute(
        "COMMENT ON TABLE stock_quotes IS "
        "'최근 종가 캐시 (KRX, 전 영업일 기준이며 실시간이 아니다). 등락률은 계산. 한 종목당 한 행만 유지'"
    )


def downgrade() -> None:
    raise RuntimeError("마이그레이션은 되돌리지 않습니다. 개발 DB를 새로 만드세요.")
