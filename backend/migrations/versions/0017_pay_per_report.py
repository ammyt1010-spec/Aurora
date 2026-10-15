"""Company report quotations and editable worker-based price bands."""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None
SCHEMA = "colmena"


def upgrade() -> None:
    op.create_table(
        "report_tariffs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("min_workers", sa.Integer(), nullable=False),
        sa.Column("max_workers", sa.Integer(), nullable=True),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PEN"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by_user_id", sa.BigInteger(), sa.ForeignKey(f"{SCHEMA}.users.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("min_workers > 0", name="ck_tariff_min_positive"),
        sa.CheckConstraint("max_workers IS NULL OR max_workers >= min_workers", name="ck_tariff_range"),
        sa.CheckConstraint("price >= 0", name="ck_tariff_price_nonnegative"),
        schema=SCHEMA,
    )
    op.create_table(
        "report_orders",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("study_id", sa.BigInteger(), sa.ForeignKey(f"{SCHEMA}.studies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), sa.ForeignKey(f"{SCHEMA}.organizations.id"), nullable=False),
        sa.Column("tariff_id", sa.BigInteger(), sa.ForeignKey(f"{SCHEMA}.report_tariffs.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.BigInteger(), sa.ForeignKey(f"{SCHEMA}.users.id"), nullable=False),
        sa.Column("workers", sa.Integer(), nullable=False),
        sa.Column("tariff_min_workers", sa.Integer(), nullable=False),
        sa.Column("tariff_max_workers", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PEN"),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_PAYMENT"),
        sa.Column("payment_reference", sa.String(120), nullable=True),
        sa.Column("confirmed_by_user_id", sa.BigInteger(), sa.ForeignKey(f"{SCHEMA}.users.id"), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("workers > 0", name="ck_order_workers_positive"),
        sa.CheckConstraint("amount >= 0", name="ck_order_amount_nonnegative"),
        schema=SCHEMA,
    )
    op.add_column("report_runs", sa.Column("billing_order_id", sa.BigInteger(), nullable=True), schema=SCHEMA)
    op.create_foreign_key("fk_report_runs_order", "report_runs", "report_orders",
                          ["billing_order_id"], ["id"], source_schema=SCHEMA, referent_schema=SCHEMA)
    op.create_unique_constraint("uq_report_runs_billing_order", "report_runs", ["billing_order_id"], schema=SCHEMA)
    op.create_index("ix_report_orders_study_created", "report_orders", ["study_id", "created_at"], schema=SCHEMA)
    op.create_index("ix_report_orders_status", "report_orders", ["status", "created_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_report_orders_status", table_name="report_orders", schema=SCHEMA)
    op.drop_index("ix_report_orders_study_created", table_name="report_orders", schema=SCHEMA)
    op.drop_constraint("uq_report_runs_billing_order", "report_runs", schema=SCHEMA)
    op.drop_constraint("fk_report_runs_order", "report_runs", schema=SCHEMA, type_="foreignkey")
    op.drop_column("report_runs", "billing_order_id", schema=SCHEMA)
    op.drop_table("report_orders", schema=SCHEMA)
    op.drop_table("report_tariffs", schema=SCHEMA)
