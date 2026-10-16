"""Commercial integrity: immutable snapshots, headcount source and enterprise license indexes."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None
SCHEMA = "colmena"


def upgrade():
    # 1. Add headcount_source and snapshot_data to report_orders
    op.add_column(
        "report_orders",
        sa.Column("headcount_source", sa.String(60), nullable=False, server_default="ESTUDIO_DECLARADO"),
        schema=SCHEMA,
    )
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
    op.add_column(
        "report_orders",
        sa.Column("snapshot_data", json_type, nullable=True),
        schema=SCHEMA,
    )

    # 2. Add performance & audit indexes
    op.create_index(
        "ix_report_orders_org_status",
        "report_orders",
        ["organization_id", "status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_report_orders_study_status",
        "report_orders",
        ["study_id", "status"],
        schema=SCHEMA,
    )


def downgrade():
    op.drop_index("ix_report_orders_study_status", table_name="report_orders", schema=SCHEMA)
    op.drop_index("ix_report_orders_org_status", table_name="report_orders", schema=SCHEMA)
    op.drop_column("report_orders", "snapshot_data", schema=SCHEMA)
    op.drop_column("report_orders", "headcount_source", schema=SCHEMA)
