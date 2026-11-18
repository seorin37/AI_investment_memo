"""merge news and market migrations

Revision ID: 511517f9874b
Revises: 0006, 0006_market
Create Date: 2026-10-23 14:13:22.931917

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '511517f9874b'
down_revision: Union[str, Sequence[str], None] = ('0006', '0006_market')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
