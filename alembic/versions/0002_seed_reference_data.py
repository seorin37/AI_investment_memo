"""seed: plan_limits, news_sources, 개발용 초기 종목 26개 (코스피만)"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 요금제별 AI 추적 한도 (pro는 NULL = 제한 없음)
    op.execute("""
        INSERT INTO plan_limits (plan, max_active_tracking_items) VALUES
          ('free', 10),
          ('pro', NULL)
        ON CONFLICT (plan) DO NOTHING
    """)

    # 뉴스 매체 4곳
    op.execute("""
        INSERT INTO news_sources (code, name) VALUES
          ('sedaily',  '서울경제'),
          ('mk',       '매일경제'),
          ('hankyung', '한국경제'),
          ('yonhap',   '연합뉴스')
        ON CONFLICT (code) DO NOTHING
    """)

    # 개발용 초기 종목 26개 (dart_corp_code, shares_outstanding은 수집 단계에서 채운다)
    op.execute("""
        INSERT INTO stocks (symbol, name, market, sector) VALUES
          ('005930', '삼성전자',            'KOSPI',  'general'),
          ('000660', 'SK하이닉스',          'KOSPI',  'general'),
          ('373220', 'LG에너지솔루션',      'KOSPI',  'general'),
          ('207940', '삼성바이오로직스',    'KOSPI',  'general'),
          ('005380', '현대차',              'KOSPI',  'general'),
          ('000270', '기아',                'KOSPI',  'general'),
          ('068270', '셀트리온',            'KOSPI',  'general'),
          ('035420', 'NAVER',               'KOSPI',  'general'),
          ('035720', '카카오',              'KOSPI',  'general'),
          ('005490', 'POSCO홀딩스',         'KOSPI',  'general'),
          ('051910', 'LG화학',              'KOSPI',  'general'),
          ('006400', '삼성SDI',             'KOSPI',  'general'),
          ('028260', '삼성물산',            'KOSPI',  'general'),
          ('012330', '현대모비스',          'KOSPI',  'general'),
          ('015760', '한국전력',            'KOSPI',  'general'),
          ('259960', '크래프톤',            'KOSPI',  'general'),
          ('036570', '엔씨소프트',          'KOSPI',  'general'),
          ('352820', '하이브',              'KOSPI',  'general'),
          ('096770', 'SK이노베이션',        'KOSPI',  'general'),
          ('003490', '대한항공',            'KOSPI',  'general'),
          ('090430', '아모레퍼시픽',        'KOSPI',  'general'),
          ('034020', '두산에너빌리티',      'KOSPI',  'general'),
          ('105560', 'KB금융',              'KOSPI',  'financial'),
          ('055550', '신한지주',            'KOSPI',  'financial'),
          ('086790', '하나금융지주',        'KOSPI',  'financial'),
          ('032830', '삼성생명',            'KOSPI',  'financial')
        ON CONFLICT (symbol) DO NOTHING
    """)


def downgrade() -> None:
    raise RuntimeError("시드 데이터는 되돌리지 않습니다.")
