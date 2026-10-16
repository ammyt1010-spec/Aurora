"""Restricted headcount evidence approval and enterprise audit API."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


EvidenceSource = Literal["PLANILLA_OFICIAL_EMPRESA", "AUDITORIA_RRHH"]


class HeadcountEvidenceApprove(BaseModel):
    source_type: EvidenceSource
    workers: int = Field(ge=1, le=10_000_000)
    # The document stays in a separately secured record repository.
    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_reference: str = Field(min_length=6, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    valid_until: datetime

    @field_validator("valid_until")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("La vigencia debe incluir zona horaria.")
        return value


class HeadcountEvidenceRead(BaseModel):
    id: int
    organization_id: int
    source_type: EvidenceSource
    workers: int
    document_sha256: str
    evidence_reference: str
    verified_by_user_id: int
    verified_at: datetime
    valid_until: datetime
    revoked_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
