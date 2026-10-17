from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class InvitationIssueRequest(BaseModel):
    count: int = Field(gt=0, le=1000)


class InvitationBatchRead(BaseModel):
    tokens: list[str]


class InvitationSummaryRead(BaseModel):
    total: int
    pending: int
    consumed: int
    expired: int
    revoked: int | None = None


class InvitationRead(BaseModel):
    id: int
    study_id: int
    status: str
    sent_at: datetime | None = None
    consumed_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict = Field(default_factory=dict, validation_alias="metadata_")

    model_config = ConfigDict(from_attributes=True)
