"""Registra el único informe gratuito de Aurora por empresa."""

from alembic import op
import sqlalchemy as sa


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

SCHEMA = "colmena"


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("free_report_claimed_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "organizations",
        sa.Column("free_report_project_id", sa.BigInteger(), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_organizations_free_report_project_id",
        "organizations",
        "projects",
        ["free_report_project_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_organizations_free_report_project_id",
        "organizations",
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_column("organizations", "free_report_project_id", schema=SCHEMA)
    op.drop_column("organizations", "free_report_claimed_at", schema=SCHEMA)
