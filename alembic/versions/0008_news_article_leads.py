"""뉴스 리드 보충 테이블 (요약이 없거나 짧은 기사의 첫 문단)

Revision ID: 0008_news_article_leads
Revises: 0007_disclosure_embeddings
Create Date: 2026-10-27

RSS 요약이 비었거나 40자 미만인 기사만 기사 링크(link) 또는 네이버 검색 API(naver)로
첫 2~3문장(최대 300자)을 보충한다. 임베딩 입력에만 쓰고 화면·LLM 근거에는 쓰지 않으므로
news_articles.summary와 섞지 않고 별도 테이블에 둔다.
source='none'은 보충 대상 매체가 아니거나 스위치가 꺼져 skipped로 끝난 경우다.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008_news_article_leads"
down_revision: Union[str, Sequence[str], None] = "0007_disclosure_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
CREATE TABLE news_article_leads (
  news_id      bigint      PRIMARY KEY REFERENCES news_articles(id) ON DELETE CASCADE,
  source       text        NOT NULL CHECK (source IN ('link', 'naver', 'none')),
  status       text        NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'ok', 'failed', 'skipped')),
  lead_text    text        CHECK (lead_text IS NULL OR char_length(lead_text) BETWEEN 1 AND 300),
  attempts     smallint    NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  http_status  integer,
  last_error   text,
  fetched_at   timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CHECK ((status = 'ok') = (lead_text IS NOT NULL))
);
CREATE INDEX news_article_leads_pending_idx ON news_article_leads (news_id) WHERE status = 'pending';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS news_article_leads")
