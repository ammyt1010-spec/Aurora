from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.organizations import OrganizationCreate

ProjectType = Literal["ACADEMIC", "CENSO", "CUSTOM", "RESEARCH"]
InstrumentKind = Literal["SHORT", "MEDIUM"]
AnalyticsPlanCode = Literal["STANDARD", "ADVANCED", "PREMIUM"]


class CensopasStudyConfig(BaseModel):
    instrument_version: InstrumentKind = "SHORT"
    instrument_version_id: int | None = Field(default=None, gt=0)
    analytics_plan: AnalyticsPlanCode = "STANDARD"
    workplace_name: str | None = Field(default=None, max_length=200)
    population_invited: int | None = Field(default=None, ge=1)
    period_start: date | None = None
    period_end: date | None = None
    settings: dict = Field(default_factory=dict)
    requires_invitation: bool = False


class ProjectCreate(BaseModel):
    owner_user_id: int
    organization_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    project_type: ProjectType
    description: str | None = None
    metadata: dict = Field(default_factory=dict)
    new_organization: OrganizationCreate | None = None
    censopas_study: CensopasStudyConfig | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    metadata: dict | None = None


class ProjectRead(BaseModel):
    id: int
    public_id: uuid.UUID
    owner_user_id: int
    organization_id: int | None
    name: str
    project_type: str
    description: str | None
    status: str
    # El atributo Python en el modelo ORM es `metadata_` (para no chocar con
    # `DeclarativeBase.metadata`); aquí se lee desde ahí pero se expone como
    # `metadata` en la API (harness §7).
    metadata: dict = Field(validation_alias=AliasChoices("metadata_", "metadata"))
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
