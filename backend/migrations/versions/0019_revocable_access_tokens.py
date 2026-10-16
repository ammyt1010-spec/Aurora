"""Persist JWT logout revocations across browser sessions and API workers."""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None
SCHEMA = "colmena"


def upgrade():
    op.create_table(
        "revoked_access_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], [f"{SCHEMA}.users.id"], ondelete="CASCADE"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_revoked_access_tokens_expires_at", "revoked_access_tokens",
        ["expires_at"], schema=SCHEMA,
    )


def downgrade():
    op.drop_index(
        "ix_revoked_access_tokens_expires_at",
        table_name="revoked_access_tokens", schema=SCHEMA,
    )
    op.drop_table("revoked_access_tokens", schema=SCHEMA)
