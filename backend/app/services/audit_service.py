"""Auditoría mínima (harness §40).

Registra creación/edición de instrumento, versión, ítem, dimensión y
variable. Se llama desde los demás servicios de escritura, nunca desde los
routers directamente.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: int | None,
        user_id: int | None = None,
        project_id: int | None = None,
        organization_id: int | None = None,
        before_data: dict | None = None,
        after_data: dict | None = None,
    ) -> None:
        entry = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            project_id=project_id,
            organization_id=organization_id,
            before_data=before_data,
            after_data=after_data,
        )
        self.session.add(entry)
        await self.session.flush()
