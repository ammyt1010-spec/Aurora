"""Informes PDF de batería ya pagados.

Revision ID: 0027
Revises: 0026
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consolidated_bundle_reports",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("bundle_id", sa.BigInteger(), sa.ForeignKey("colmena.evaluation_bundles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("colmena.users.id"), nullable=False),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("data_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="colmena",
    )
    op.create_index("ix_bundle_reports_bundle", "consolidated_bundle_reports", ["bundle_id"], schema="colmena")


def downgrade() -> None:
    op.drop_index("ix_bundle_reports_bundle", table_name="consolidated_bundle_reports", schema="colmena")
    op.drop_table("consolidated_bundle_reports", schema="colmena")
