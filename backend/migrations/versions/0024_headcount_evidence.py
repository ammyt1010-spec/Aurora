"""Append-only headcount evidence audit ledger for operator-reviewed enterprise workforce."""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None
SCHEMA = "colmena"


def upgrade():
    op.create_table(
        "headcount_evidence",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("organization_id", sa.BigInteger(), sa.ForeignKey("colmena.organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("workers", sa.Integer(), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("evidence_reference", sa.String(120), nullable=False),
        sa.Column("verified_by_user_id", sa.BigInteger(), sa.ForeignKey("colmena.users.id"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by_user_id", sa.BigInteger(), sa.ForeignKey("colmena.users.id")),
        sa.CheckConstraint("workers > 0", name="ck_headcount_evidence_workers_positive"),
        sa.CheckConstraint("valid_until > verified_at", name="ck_headcount_evidence_validity"),
        sa.UniqueConstraint("organization_id", "source_type", "document_sha256", name="uq_headcount_evidence_source_hash"),
        schema=SCHEMA,
    )
    op.create_index("ix_headcount_evidence_org_source", "headcount_evidence", ["organization_id", "source_type"], schema=SCHEMA)


def downgrade():
    op.drop_index("ix_headcount_evidence_org_source", table_name="headcount_evidence", schema=SCHEMA)
    op.drop_table("headcount_evidence", schema=SCHEMA)
