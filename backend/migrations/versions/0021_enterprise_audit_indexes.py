"""Indexes for bounded enterprise audit feeds without changing stored events."""
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None
SCHEMA = "colmena"


def upgrade():
    op.create_index(
        "ix_audit_logs_org_id_id",
        "audit_logs", ["organization_id", "id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_audit_logs_project_id_id",
        "audit_logs", ["project_id", "id"],
        schema=SCHEMA,
    )


def downgrade():
    op.drop_index("ix_audit_logs_project_id_id", table_name="audit_logs", schema=SCHEMA)
    op.drop_index("ix_audit_logs_org_id_id", table_name="audit_logs", schema=SCHEMA)
