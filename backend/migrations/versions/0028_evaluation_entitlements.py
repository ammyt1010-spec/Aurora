"""Cuatro evaluaciones completas gratuitas por cuenta.

Revision ID: 0028
Revises: 0027
"""

from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_entitlements",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("colmena.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("study_id", sa.BigInteger(), sa.ForeignKey("colmena.studies.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("access_kind", sa.String(8), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("colmena.report_orders.id", ondelete="SET NULL"), unique=True),
        sa.Column("free_report_id", sa.BigInteger(), sa.ForeignKey("colmena.report_runs.id", ondelete="SET NULL"), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("access_kind IN ('FREE', 'PAID')", name="ck_evaluation_access_kind"),
        sa.CheckConstraint("status IN ('ACTIVE', 'PENDING_PAYMENT')", name="ck_evaluation_access_status"),
        schema="colmena",
    )
    op.create_index("ix_evaluation_entitlements_user_id", "evaluation_entitlements", ["user_id"], schema="colmena")


def downgrade() -> None:
    op.drop_index("ix_evaluation_entitlements_user_id", table_name="evaluation_entitlements", schema="colmena")
    op.drop_table("evaluation_entitlements", schema="colmena")
