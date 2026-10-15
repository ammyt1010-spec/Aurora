"""Indexes for large psychometric datasets and operational history."""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

_INDEXES = (
    ("ix_aurora_response_study_question_session", "responses",
     ["study_id", "question_id", "response_session_id"]),
    ("ix_aurora_session_study_validation", "response_sessions",
     ["study_id", "validation_status"]),
    ("ix_aurora_analysis_study_type_status", "analysis_runs",
     ["study_id", "analysis_type", "status"]),
    ("ix_aurora_invitations_study_status", "study_invitations",
     ["study_id", "status"]),
    ("ix_aurora_exports_study_created", "exports",
     ["study_id", "created_at"]),
    ("ix_aurora_reports_study_created", "report_runs",
     ["study_id", "created_at"]),
)


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns, schema="colmena")


def downgrade() -> None:
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table, schema="colmena")
