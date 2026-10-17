from __future__ import annotations

import datetime as dt
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import metadata_field

InstrumentVersionStatus = Literal[
    "DRAFT", "VALIDATING", "AUTHORIZED", "TEST", "ACTIVE", "USED", "CLOSED", "LOCKED"
]
InstrumentStatus = Literal[
    "DRAFT", "VALIDATING", "AUTHORIZED", "ACTIVE", "LOCKED", "ARCHIVED"
]


class InstrumentCreate(BaseModel):
    project_id: int | None = None
    owner_user_id: int | None = None
    organization_id: int | None = None
    code: str | None = None
    name: str = Field(min_length=1, max_length=255)
    instrument_type: str | None = None
    discipline: str = "PSICOSOCIAL"
    description: str | None = None
    author: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    reproduction_terms: str | None = None
    method_code: str | None = None
    is_system: bool = False
    status: str = "DRAFT"
    metadata: dict = Field(default_factory=dict)


class InstrumentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    instrument_type: str | None = None
    discipline: str | None = None
    description: str | None = None
    author: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    reproduction_terms: str | None = None
    method_code: str | None = None
    status: str | None = None
    metadata: dict | None = None


class InstrumentRead(BaseModel):
    id: int
    public_id: uuid.UUID
    project_id: int | None
    owner_user_id: int | None
    organization_id: int | None
    code: str | None
    name: str
    instrument_type: str | None
    discipline: str = "PSICOSOCIAL"
    description: str | None
    author: str | None = None
    source_name: str | None
    source_url: str | None
    reproduction_terms: str | None = None
    method_code: str | None = None
    is_system: bool
    status: str
    metadata: dict = metadata_field()
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstrumentVersionCreate(BaseModel):
    version_code: str = Field(min_length=1, max_length=80)
    version_name: str | None = None
    edition: str | None = None
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None
    status: InstrumentVersionStatus = "DRAFT"
    source_reference: str | None = None
    reproduction_restrictions: str | None = None
    validation_notes: str | None = None
    config: dict = Field(default_factory=dict)
    methodological_rules: dict = Field(default_factory=dict)


class InstrumentVersionUpdate(BaseModel):
    version_name: str | None = None
    edition: str | None = None
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None
    status: InstrumentVersionStatus | None = None
    scoring_status: str | None = None
    source_reference: str | None = None
    reproduction_restrictions: str | None = None
    validation_notes: str | None = None
    config: dict | None = None
    methodological_rules: dict | None = None


class InstrumentVersionRead(BaseModel):
    id: int
    public_id: uuid.UUID
    instrument_id: int
    version_code: str
    version_name: str | None
    edition: str | None
    valid_from: dt.date | None
    valid_to: dt.date | None
    status: str
    scoring_status: str
    source_reference: str | None
    reproduction_restrictions: str | None = None
    validation_notes: str | None = None
    config: dict
    methodological_rules: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MethodologicalValidationResult(BaseModel):
    version_id: int
    version_code: str
    is_valid: bool
    technical_completeness: bool = False
    historical_version_locked: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    status: str
    scoring_status: str


class InstrumentStatusUpdateRequest(BaseModel):
    status: str
    notes: str | None = None


class EditableStatus(BaseModel):
    """Respuesta de disponibilidad de edición (harness §56)."""

    editable: bool
    reason: str | None = None


class InstrumentVersionCloneRequest(BaseModel):
    version_code: str = Field(min_length=1, max_length=80)
    version_name: str | None = None


# --- Árbol / matriz (§57, §58) -------------------------------------------------


class InstrumentTreeItem(BaseModel):
    id: int
    code: str | None
    question_text: str
    short_label: str | None
    question_type: str
    is_scored: bool
    research_role: str | None
    option_set_id: int | None
    weight: float
    scoring_direction: str | None
    sort_order: int | None


class InstrumentTreeConstruct(BaseModel):
    id: int
    code: str
    name: str
    construct_type: str
    sort_order: int | None
    subdimensions: list["InstrumentTreeConstruct"] = Field(default_factory=list)
    items: list[InstrumentTreeItem] = Field(default_factory=list)


class InstrumentTreeVariable(BaseModel):
    id: int
    code: str
    name: str
    role: str
    sort_order: int | None
    direct_items: list[InstrumentTreeItem] = Field(default_factory=list)
    dimensions: list[InstrumentTreeConstruct] = Field(default_factory=list)


class InstrumentTree(BaseModel):
    instrument_version_id: int
    editable: bool
    lock_reason: str | None = None
    variables: list[InstrumentTreeVariable] = Field(default_factory=list)


class ConstructMatrixRow(BaseModel):
    question_id: int
    item_code: str | None
    question_text: str
    question_type: str
    is_scored: bool
    research_role: str | None
    variable_code: str | None
    construct_id: int
    construct_code: str
    construct_name: str
    construct_type: str
    research_variable_code: str | None
    research_variable_name: str | None
    dimension_code: str | None
    dimension_name: str | None
    subdimension_code: str | None
    subdimension_name: str | None
    weight: float
    scoring_direction: str | None
    status: str


class ConstructMatrix(BaseModel):
    instrument_version_id: int
    editable: bool
    rows: list[ConstructMatrixRow]
