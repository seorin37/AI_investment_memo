"""0015 뉴스 본문·청크 마이그레이션 내용 확인. DB 없이 파일만 읽는다 (실제 적용은 로컬 DB에서 따로 확인)."""
import re
from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[4] / "alembic" / "versions" / "0015_news_article_bodies.py"


def text():
    return MIGRATION.read_text(encoding="utf-8")


def sql():
    return " ".join(text().split("UPGRADE_SQL")[1].split())                     # 공백을 하나로 모아 비교한다


def test_revision_chain_follows_0014():
    src = text()
    assert 'revision: str = "0015_news_article_bodies"' in src
    assert 'down_revision: Union[str, Sequence[str], None] = "0014_disclosure_events"' in src


def test_bodies_table_keys_and_checks():
    up = sql()
    assert "news_id bigint PRIMARY KEY REFERENCES news_articles(id) ON DELETE CASCADE" in up
    assert "source_code text NOT NULL REFERENCES news_sources(code)" in up
    assert "CHECK (fetch_method IN ('link', 'naver'))" in up
    assert "CHECK (char_length(body) >= 100)" in up
    assert "CREATE INDEX ix_news_article_bodies_source_code ON news_article_bodies (source_code)" in up
    assert "CREATE INDEX ix_news_article_bodies_body_hash ON news_article_bodies (body_hash)" in up
    assert "is_paid" not in up                                                  # 유료 기사는 수집 단계에서 뺀다


def test_chunks_embedding_columns_match_disclosure_chunks():                    # 0007과 같은 이름·규칙
    up = sql()
    assert "REFERENCES news_article_bodies(news_id) ON DELETE CASCADE" in up
    assert "CHECK (token_count BETWEEN 1 AND 512)" in up and "UNIQUE (news_id, chunk_index)" in up
    for col in ("dense_embedding vector(1024)", "sparse_embedding jsonb", "embedding_model text",
                "embedding_revision text", "embedding_config_hash text", "embedded_at timestamptz"):
        assert col in up, col
    assert "embedding_dense" not in up and "embedding_sparse" not in up
    assert ("CONSTRAINT ck_news_chunks_sparse_object CHECK (sparse_embedding IS NULL OR "
            "jsonb_typeof(sparse_embedding) = 'object')") in up
    assert "CONSTRAINT ck_news_chunks_embedding_pair CHECK ((dense_embedding IS NULL) = (sparse_embedding IS NULL))" in up
    assert ("CONSTRAINT ck_news_chunks_embedding_metadata CHECK ((dense_embedding IS NULL AND embedding_model IS NULL "
            "AND embedding_revision IS NULL AND embedding_config_hash IS NULL AND embedded_at IS NULL) OR "
            "(dense_embedding IS NOT NULL AND embedding_model IS NOT NULL AND embedding_revision IS NOT NULL "
            "AND embedding_config_hash IS NOT NULL AND embedded_at IS NOT NULL))") in up
    assert "'legacy'" not in up                                                 # 새 테이블이라 legacy 예외 없음
    assert "CREATE INDEX ix_news_chunks_dense_embedding ON news_chunks USING hnsw (dense_embedding vector_cosine_ops)" in up
    assert not re.search(r"\b\w*colbert\w* (vector|jsonb|bytea|real)", up, re.I)   # colbert 컬럼은 두지 않는다


def test_downgrade_drops_chunks_before_bodies():
    down = text().split("DOWNGRADE_SQL")[1]
    assert down.index("DROP TABLE news_chunks") < down.index("DROP TABLE news_article_bodies")
