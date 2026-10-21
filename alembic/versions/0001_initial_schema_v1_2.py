"""Initial schema from the full v1.2 ERD."""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL_FILE = Path(__file__).resolve().parent.parent / "sql" / "0001_schema_full_v1_2.sql"


def upgrade() -> None:
    # Execute the full schema in one transaction through the DBAPI connection.
    raw = op.get_bind().connection.driver_connection
    raw.execute(SQL_FILE.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise RuntimeError(
        "The initial schema cannot be downgraded; recreate the development database."
    )
