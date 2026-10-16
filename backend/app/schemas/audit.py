"""Public-safe audit representations: never expose old raw before/after payloads."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    id: int
    action: str
    actor_user_id: int | None
    organization_id: int | None
    project_id: int | None
    entity_type: str | None
    entity_id: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditEventsPage(BaseModel):
    items: list[AuditEventRead]
    next_before_id: int | None
