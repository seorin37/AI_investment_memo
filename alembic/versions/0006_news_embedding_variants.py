"""뉴스 임베딩 실험용 테이블 (dense / hybrid 분리 저장)

초안: 공유 스키마를 바꾸므로 팀 합의 후 적용한다.
news_articles.embedding 은 컬럼이 하나라 dense 와 hybrid 를 같이 담을 수 없어서,
실험 동안은 이 테이블에 방식별로 저장하고 승자가 정해지면 news_articles.embedding 으로 복사한다.

TODO: revision / down_revision 을 실제 0004 파일의 값에 맞출 것 (아래는 자리표시자).
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

UPGRADE_SQL = """
CREATE TABLE news_embedding_variants (
  news_id     bigint  NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
  variant     text    NOT NULL CHECK (variant IN ('dense', 'hybrid')),
  dense       vector(1024) NOT NULL,
  sparse      jsonb,
  model       text    NOT NULL,
  embedded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (news_id, variant),
  CHECK (variant <> 'hybrid' OR sparse IS NOT NULL)
);
CREATE INDEX news_emb_dense_hnsw  ON news_embedding_variants USING hnsw (dense vector_cosine_ops) WHERE variant = 'dense';
CREATE INDEX news_emb_hybrid_hnsw ON news_embedding_variants USING hnsw (dense vector_cosine_ops) WHERE variant = 'hybrid';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS news_embedding_variants")
