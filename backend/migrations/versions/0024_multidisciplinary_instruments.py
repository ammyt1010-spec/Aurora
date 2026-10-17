"""Multidisciplinary instruments: discipline, reproduction rights, methodological rules and tariff linking.

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None
SCHEMA = "colmena"


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")

    # 1. Extend colmena.instruments for multidisciplinary capabilities
    op.add_column(
        "instruments",
        sa.Column("discipline", sa.String(80), nullable=False, server_default="PSICOSOCIAL"),
        schema=SCHEMA,
    )
    op.add_column(
        "instruments",
        sa.Column("reproduction_terms", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "instruments",
        sa.Column("author", sa.String(255), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "instruments",
        sa.Column("method_code", sa.String(50), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_instruments_org_discipline",
        "instruments",
        ["organization_id", "discipline"],
        schema=SCHEMA,
    )

    # 2. Extend colmena.instrument_versions with validation & rights
    op.add_column(
        "instrument_versions",
        sa.Column("reproduction_restrictions", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "instrument_versions",
        sa.Column("validation_notes", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "instrument_versions",
        sa.Column("methodological_rules", json_type, nullable=False, server_default="{}"),
        schema=SCHEMA,
    )

    # 3. Extend colmena.report_tariffs to link with instruments
    op.add_column(
        "report_tariffs",
        sa.Column(
            "instrument_id",
            sa.BigInteger(),
            sa.ForeignKey(f"{SCHEMA}.instruments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "report_tariffs",
        sa.Column("notes", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_report_tariffs_instrument_id",
        "report_tariffs",
        ["instrument_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_report_tariffs_instrument_id", table_name="report_tariffs", schema=SCHEMA)
    op.drop_column("report_tariffs", "notes", schema=SCHEMA)
    op.drop_column("report_tariffs", "instrument_id", schema=SCHEMA)

    op.drop_column("instrument_versions", "methodological_rules", schema=SCHEMA)
    op.drop_column("instrument_versions", "validation_notes", schema=SCHEMA)
    op.drop_column("instrument_versions", "reproduction_restrictions", schema=SCHEMA)

    op.drop_index("ix_instruments_org_discipline", table_name="instruments", schema=SCHEMA)
    op.drop_column("instruments", "method_code", schema=SCHEMA)
    op.drop_column("instruments", "author", schema=SCHEMA)
    op.drop_column("instruments", "reproduction_terms", schema=SCHEMA)
    op.drop_column("instruments", "discipline", schema=SCHEMA)
