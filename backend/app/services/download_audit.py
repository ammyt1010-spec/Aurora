"""Minimal, privacy-safe audit trail for protected file access."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study import Study
from app.services.audit_service import AuditService


async def record_file_access(
    session: AsyncSession, *, action: str, entity_type: str,
    entity_id: int, study_id: int, user_id: int | None,
) -> None:
    study = await session.get(Study, study_id)
    await AuditService(session).log(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        project_id=study.project_id if study else None,
    )
    await session.commit()
