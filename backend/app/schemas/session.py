from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class UserSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    device_family: str | None = None
    os_family: str | None = None
    browser_family: str | None = None
    ip_address: str | None = None
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    is_current: bool = False


class SessionRevokeResponse(BaseModel):
    revoked_count: int
    message: str


class SessionCleanupResponse(BaseModel):
    purged_sessions_count: int
    purged_revoked_tokens_count: int
