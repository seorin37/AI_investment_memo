"""UI 최종본 반영 (ERD v1.2)

Revision ID: 0004
Revises: 0003
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 프로필
    op.execute("ALTER TABLE users ADD COLUMN bio text")
    op.execute("ALTER TABLE users ADD COLUMN avatar_url text")

    # 피드백 별점
    op.execute("ALTER TABLE feedbacks ADD COLUMN rating smallint")
    op.execute(
        "ALTER TABLE feedbacks ADD CONSTRAINT ck_feedbacks_rating "
        "CHECK (rating IS NULL OR rating BETWEEN 1 AND 5)"
    )

    # 달력 위젯: 공통 일정(user_id NULL) / 내 일정
    op.execute("ALTER TABLE market_events ADD COLUMN user_id bigint REFERENCES users(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE market_events ADD COLUMN kind text NOT NULL DEFAULT 'market'")
    op.execute(
        "ALTER TABLE market_events ADD CONSTRAINT ck_market_events_kind "
        "CHECK (kind IN ('market', 'earnings', 'user'))"
    )
    op.execute("CREATE INDEX ix_market_events_user_date ON market_events (user_id, event_date)")

    # 참고자료 종류 + 파일 첨부
    op.execute("ALTER TABLE memo_links ADD COLUMN link_type text")
    op.execute("ALTER TABLE memo_links ADD COLUMN is_file boolean NOT NULL DEFAULT false")
    op.execute(
        "ALTER TABLE memo_links ADD CONSTRAINT ck_memo_links_link_type "
        "CHECK (link_type IS NULL OR link_type IN ('ir', 'news', 'report', 'disclosure', 'other'))"
    )

    # 기업정보 화면
    op.execute("ALTER TABLE prices_daily ADD COLUMN trading_value numeric(20,0)")
    op.execute("ALTER TABLE financials ADD COLUMN fs_div text NOT NULL DEFAULT 'consolidated'")
    op.execute(
        "ALTER TABLE financials ADD CONSTRAINT ck_financials_fs_div "
        "CHECK (fs_div IN ('consolidated', 'separate'))"
    )
    op.execute("ALTER TABLE financials ADD COLUMN capital_stock numeric(20,0)")

    # AI 연결은 일반 메모(note)만
    op.execute(
        "ALTER TABLE memos ADD CONSTRAINT ck_memos_ai_only_note "
        "CHECK (NOT ai_linked OR kind = 'note')"
    )

    # AI 업데이트 상세 화면
    op.execute(
        "ALTER TABLE tracking_updates ADD COLUMN memo_revision_id bigint "
        "REFERENCES memo_revisions(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE tracking_updates ADD COLUMN price_state text")
    op.execute(
        "ALTER TABLE tracking_updates ADD CONSTRAINT ck_tracking_updates_price_state "
        "CHECK (price_state IS NULL OR price_state IN ('near', 'away', 'reached'))"
    )
    op.execute("ALTER TABLE tracking_updates ADD COLUMN details jsonb")

    # 벡터 검색 인덱스 (코사인)
    op.execute("CREATE INDEX ix_news_articles_embedding ON news_articles USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX ix_disclosure_chunks_embedding ON disclosure_chunks USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX ix_tracking_items_embedding ON tracking_items USING hnsw (embedding vector_cosine_ops)")

    # 주석
    op.execute("COMMENT ON TABLE news_sources IS '뉴스 출처(신문사). code: sedaily(서울경제), mk(매일경제), hankyung(한국경제), yonhap(연합뉴스)'")
    op.execute("COMMENT ON COLUMN disclosure_chunks.section IS '정기보고서 항목명(예: 사업의 내용). 전문을 항목 단위로 나눠 저장'")
    op.execute("COMMENT ON COLUMN users.bio IS '설정 > 내 프로필의 한 줄 소개'")
    op.execute("COMMENT ON COLUMN users.avatar_url IS '프로필 사진 주소'")
    op.execute("COMMENT ON COLUMN feedbacks.rating IS '일반 피드백 별점 1~5, 오류 신고는 NULL'")
    op.execute("COMMENT ON COLUMN market_events.user_id IS 'NULL이면 모든 사용자에게 보이는 공통 일정, 값이 있으면 그 사용자의 내 일정'")
    op.execute("COMMENT ON COLUMN market_events.kind IS 'market(증시) / earnings(실적) / user(내 일정)'")
    op.execute("COMMENT ON COLUMN memo_links.link_type IS 'ir / news / report / disclosure / other'")
    op.execute("COMMENT ON COLUMN memo_links.is_file IS '파일 첨부면 true, url은 저장된 파일 주소'")
    op.execute("COMMENT ON COLUMN prices_daily.trading_value IS '거래대금(원). KRX 일별 시세 값'")
    op.execute("COMMENT ON COLUMN financials.fs_div IS 'consolidated(연결) / separate(별도). 화면은 연결 기준'")
    op.execute("COMMENT ON COLUMN financials.capital_stock IS '자본금. 유보율 = 이익잉여금 / 자본금 계산용'")
    op.execute("COMMENT ON COLUMN tracking_updates.memo_revision_id IS '이 업데이트를 만들 당시 메모 버전. 카드의 연결된 내 메모 표시용'")
    op.execute("COMMENT ON COLUMN tracking_updates.price_state IS '주가 업데이트 상태: near(가까워짐) / away(멀어짐) / reached(도달)'")
    op.execute("COMMENT ON COLUMN tracking_updates.details IS '화면 표시용 계산값(조건가 차이, 5거래일 등락률 등). 계산은 코드로 하고 값만 저장'")


def downgrade() -> None:
    raise RuntimeError("이 프로젝트의 마이그레이션은 되돌리지 않습니다. 새 번호로 수정하세요.")
