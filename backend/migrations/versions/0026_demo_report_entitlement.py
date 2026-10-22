"""Crédito demo atómico para cuentas habilitadas.

Revision ID: 0026
Revises: 0025
"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demo_report_usages",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("colmena.users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(22), nullable=False, server_default="RESERVED"),
        sa.Column("report_id", sa.BigInteger(), sa.ForeignKey("colmena.report_runs.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="colmena",
    )


def downgrade() -> None:
    op.drop_table("demo_report_usages", schema="colmena")
