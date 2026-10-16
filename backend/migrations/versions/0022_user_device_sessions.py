"""Inventory of active user device sessions with independent revocation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None
SCHEMA = "colmena"


def upgrade():
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False, unique=True),
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("device_family", sa.String(64), nullable=True),
        sa.Column("os_family", sa.String(64), nullable=True),
        sa.Column("browser_family", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], [f"{SCHEMA}.users.id"], ondelete="CASCADE"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_user_sessions_session_id", "user_sessions",
        ["session_id"], schema=SCHEMA,
    )
    op.create_index(
        "ix_user_sessions_user_id", "user_sessions",
        ["user_id"], schema=SCHEMA,
    )
    op.create_index(
        "ix_user_sessions_active", "user_sessions",
        ["user_id", "revoked_at", "expires_at"], schema=SCHEMA,
    )
    op.create_index(
        "ix_user_sessions_expires_at", "user_sessions",
        ["expires_at"], schema=SCHEMA,
    )


def downgrade():
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions", schema=SCHEMA)
    op.drop_index("ix_user_sessions_active", table_name="user_sessions", schema=SCHEMA)
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions", schema=SCHEMA)
    op.drop_index("ix_user_sessions_session_id", table_name="user_sessions", schema=SCHEMA)
    op.drop_table("user_sessions", schema=SCHEMA)
