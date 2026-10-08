"""Atomic rate-limit state shared between API workers."""

from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_rate_limits",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("counter", sa.Integer(), nullable=False),
        schema="colmena",
    )


def downgrade() -> None:
    op.drop_table("public_rate_limits", schema="colmena")
