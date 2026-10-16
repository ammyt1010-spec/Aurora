"""Invalidate all active account JWTs with an atomic per-user version counter."""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None
SCHEMA = "colmena"


def upgrade():
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
        schema=SCHEMA,
    )


def downgrade():
    op.drop_column("users", "session_version", schema=SCHEMA)
