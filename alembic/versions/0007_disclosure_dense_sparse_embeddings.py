"""store disclosure dense and sparse embeddings in PostgreSQL

Revision ID: 0007_disclosure_embeddings
Revises: 511517f9874b
Create Date: 2026-10-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007_disclosure_embeddings"
down_revision: Union[str, Sequence[str], None] = "511517f9874b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_disclosure_chunks_embedding", table_name="disclosure_chunks")
    op.alter_column("disclosure_chunks", "embedding", new_column_name="dense_embedding")
    op.add_column("disclosure_chunks", sa.Column("sparse_embedding", postgresql.JSONB(), nullable=True))
    op.add_column("disclosure_chunks", sa.Column("embedding_model", sa.Text(), nullable=True))
    op.add_column("disclosure_chunks", sa.Column("embedding_revision", sa.Text(), nullable=True))
    op.add_column("disclosure_chunks", sa.Column("embedding_config_hash", sa.Text(), nullable=True))
    op.add_column("disclosure_chunks", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))
    # 기존 dense 값은 보존한다. sparse가 NULL인 legacy 행은 파이프라인이 재임베딩한다.
    op.execute(
        "UPDATE disclosure_chunks SET embedding_model = 'legacy', embedding_revision = 'unknown', "
        "embedding_config_hash = 'legacy', embedded_at = now() WHERE dense_embedding IS NOT NULL"
    )
    op.create_index(
        "ix_disclosure_chunks_dense_embedding",
        "disclosure_chunks",
        ["dense_embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"dense_embedding": "vector_cosine_ops"},
    )
    op.create_check_constraint(
        "ck_disclosure_chunks_sparse_object",
        "disclosure_chunks",
        "sparse_embedding IS NULL OR jsonb_typeof(sparse_embedding) = 'object'",
    )
    op.create_check_constraint(
        "ck_disclosure_chunks_embedding_pair",
        "disclosure_chunks",
        "(dense_embedding IS NULL AND sparse_embedding IS NULL) OR "
        "(dense_embedding IS NOT NULL AND sparse_embedding IS NOT NULL) OR "
        "(dense_embedding IS NOT NULL AND sparse_embedding IS NULL AND embedding_model = 'legacy')",
    )
    op.create_check_constraint(
        "ck_disclosure_chunks_embedding_metadata",
        "disclosure_chunks",
        "(dense_embedding IS NULL AND embedding_model IS NULL AND embedding_revision IS NULL "
        "AND embedding_config_hash IS NULL AND embedded_at IS NULL) OR "
        "(dense_embedding IS NOT NULL AND embedding_model IS NOT NULL AND embedding_revision IS NOT NULL "
        "AND embedding_config_hash IS NOT NULL AND embedded_at IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_disclosure_chunks_embedding_metadata", "disclosure_chunks", type_="check")
    op.drop_constraint("ck_disclosure_chunks_embedding_pair", "disclosure_chunks", type_="check")
    op.drop_constraint("ck_disclosure_chunks_sparse_object", "disclosure_chunks", type_="check")
    op.drop_index("ix_disclosure_chunks_dense_embedding", table_name="disclosure_chunks")
    op.drop_column("disclosure_chunks", "embedded_at")
    op.drop_column("disclosure_chunks", "embedding_config_hash")
    op.drop_column("disclosure_chunks", "embedding_revision")
    op.drop_column("disclosure_chunks", "embedding_model")
    op.drop_column("disclosure_chunks", "sparse_embedding")
    op.alter_column("disclosure_chunks", "dense_embedding", new_column_name="embedding")
    op.create_index(
        "ix_disclosure_chunks_embedding",
        "disclosure_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
