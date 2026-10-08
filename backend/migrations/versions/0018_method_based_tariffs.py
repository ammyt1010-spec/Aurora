"""Tarifarios específicos por instrumento y tramos Cotizar sin precio."""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None
SCHEMA = "colmena"


def upgrade():
    op.add_column("report_tariffs", sa.Column("method_code", sa.String(50), nullable=False, server_default="SUSESO_ISTAS21_BREVE"), schema=SCHEMA)
    op.add_column("report_tariffs", sa.Column("pricing_mode", sa.String(10), nullable=False, server_default="FIXED"), schema=SCHEMA)
    op.alter_column("report_tariffs", "price", existing_type=sa.Numeric(14, 2), nullable=True, schema=SCHEMA)
    op.drop_constraint("ck_tariff_price_nonnegative", "report_tariffs", schema=SCHEMA, type_="check")
    op.create_check_constraint("ck_tariff_price_nonnegative", "report_tariffs", "price IS NULL OR price >= 0", schema=SCHEMA)
    op.create_check_constraint("ck_tariff_mode_price", "report_tariffs",
        "(pricing_mode = 'QUOTE' AND price IS NULL) OR (pricing_mode = 'FIXED' AND price > 0)", schema=SCHEMA)
    op.add_column("report_orders", sa.Column("method_code", sa.String(50), nullable=False, server_default="SUSESO_ISTAS21_BREVE"), schema=SCHEMA)
    op.add_column("report_orders", sa.Column("pricing_mode", sa.String(10), nullable=False, server_default="FIXED"), schema=SCHEMA)
    op.alter_column("report_orders", "amount", existing_type=sa.Numeric(14, 2), nullable=True, schema=SCHEMA)
    op.drop_constraint("ck_order_amount_nonnegative", "report_orders", schema=SCHEMA, type_="check")
    op.create_check_constraint("ck_order_amount_nonnegative", "report_orders", "amount IS NULL OR amount >= 0", schema=SCHEMA)
    op.create_index("ix_report_tariffs_method_workers", "report_tariffs",
                    ["method_code", "min_workers", "active"], schema=SCHEMA)


def downgrade():
    op.drop_index("ix_report_tariffs_method_workers", table_name="report_tariffs", schema=SCHEMA)
    op.drop_constraint("ck_order_amount_nonnegative", "report_orders", schema=SCHEMA, type_="check")
    op.alter_column("report_orders", "amount", existing_type=sa.Numeric(14, 2), nullable=False, schema=SCHEMA)
    op.create_check_constraint("ck_order_amount_nonnegative", "report_orders", "amount >= 0", schema=SCHEMA)
    op.drop_column("report_orders", "pricing_mode", schema=SCHEMA)
    op.drop_column("report_orders", "method_code", schema=SCHEMA)
    op.drop_constraint("ck_tariff_mode_price", "report_tariffs", schema=SCHEMA, type_="check")
    op.drop_constraint("ck_tariff_price_nonnegative", "report_tariffs", schema=SCHEMA, type_="check")
    op.alter_column("report_tariffs", "price", existing_type=sa.Numeric(14, 2), nullable=False, schema=SCHEMA)
    op.create_check_constraint("ck_tariff_price_nonnegative", "report_tariffs", "price >= 0", schema=SCHEMA)
    op.drop_column("report_tariffs", "pricing_mode", schema=SCHEMA)
    op.drop_column("report_tariffs", "method_code", schema=SCHEMA)
