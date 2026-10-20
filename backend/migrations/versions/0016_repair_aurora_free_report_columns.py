"""Repara las columnas de gratuidad cuando 0015 quedó sellada sin DDL."""

from alembic import op


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE colmena.organizations
        ADD COLUMN IF NOT EXISTS free_report_claimed_at TIMESTAMPTZ NULL
        """
    )
    op.execute(
        """
        ALTER TABLE colmena.organizations
        ADD COLUMN IF NOT EXISTS free_report_project_id BIGINT NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_organizations_free_report_project_id'
                  AND conrelid = 'colmena.organizations'::regclass
            ) THEN
                ALTER TABLE colmena.organizations
                ADD CONSTRAINT fk_organizations_free_report_project_id
                FOREIGN KEY (free_report_project_id)
                REFERENCES colmena.projects(id)
                ON DELETE SET NULL;
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    # 0015 es la migración propietaria de estas columnas. Esta reparación no
    # las elimina al retroceder para no romper instalaciones donde sí existían.
    pass
