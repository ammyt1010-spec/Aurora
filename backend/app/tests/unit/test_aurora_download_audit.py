import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.services.download_audit import record_file_access


@pytest.mark.asyncio
async def test_file_access_audited_without_sensitive_content(session, seed_project, seed_user):
    await record_file_access(session, action="REPORT_DOWNLOADED", entity_type="report",
                             entity_id=24, study_id=99999, user_id=seed_user.id)
    record = (await session.execute(
        select(AuditLog).where(AuditLog.entity_type == "report", AuditLog.entity_id == 24)
    )).scalar_one()
    assert record.user_id == seed_user.id
    assert record.before_data is None and record.after_data is None
