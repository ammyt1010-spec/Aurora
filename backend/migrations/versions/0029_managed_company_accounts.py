"""First-class managed-company account relation for self-registration and administration."""

from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("managed_company_id", sa.BigInteger(), nullable=True), schema="colmena")
    op.create_foreign_key(
        "fk_users_managed_company", "users", "organizations",
        ["managed_company_id"], ["id"], source_schema="colmena", referent_schema="colmena",
        ondelete="SET NULL",
    )
    op.execute("""
        UPDATE colmena.users
        SET managed_company_id = (metadata->>'managed_company_id')::bigint
        WHERE metadata ? 'managed_company_id'
          AND metadata->>'managed_company_id' ~ '^[0-9]+$'
          AND EXISTS (
              SELECT 1 FROM colmena.organizations o
              WHERE o.id = (metadata->>'managed_company_id')::bigint
          )
    """)
    op.create_index(
        "uq_users_managed_company_id", "users", ["managed_company_id"],
        schema="colmena", unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_users_managed_company_id", table_name="users", schema="colmena")
    op.drop_constraint("fk_users_managed_company", "users", schema="colmena", type_="foreignkey")
    op.drop_column("users", "managed_company_id", schema="colmena")
