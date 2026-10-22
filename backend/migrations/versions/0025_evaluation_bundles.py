"""Baterías públicas de múltiples estudios, sin fusionar sus respuestas.

Revision ID: 0025
Revises: 0024
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None
SCHEMA = "colmena"


def upgrade() -> None:
    op.create_table(
        "evaluation_bundles",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("colmena.projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), sa.ForeignKey("colmena.organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("colmena.users.id"), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("study_ids", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="PUBLISHED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index("ix_evaluation_bundles_company", "evaluation_bundles", ["organization_id", "project_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_evaluation_bundles_company", table_name="evaluation_bundles", schema=SCHEMA)
    op.drop_table("evaluation_bundles", schema=SCHEMA)
