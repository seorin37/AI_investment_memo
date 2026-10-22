
"""Extend market_indices with OHLCV and market metrics.

Revision ID: 0006_market
Revises: 0005
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_market"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_indices",
        sa.Column("open", sa.Numeric(14, 4), nullable=True),
    )
    op.add_column(
        "market_indices",
        sa.Column("high", sa.Numeric(14, 4), nullable=True),
    )
    op.add_column(
        "market_indices",
        sa.Column("low", sa.Numeric(14, 4), nullable=True),
    )
    op.add_column(
        "market_indices",
        sa.Column("volume", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "market_indices",
        sa.Column("trade_value", sa.Numeric(22, 0), nullable=True),
    )
    op.add_column(
        "market_indices",
        sa.Column("market_cap", sa.Numeric(22, 0), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("market_indices", "market_cap")
    op.drop_column("market_indices", "trade_value")
    op.drop_column("market_indices", "volume")
    op.drop_column("market_indices", "low")
    op.drop_column("market_indices", "high")
    op.drop_column("market_indices", "open")
