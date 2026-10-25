from __future__ import annotations

import datetime as dt
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import metadata_field

Direction = Literal["HIGHER_BETTER", "LOWER_BETTER"]


class ScoringRuleCreate(BaseModel):
    question_id: int | None = None
    construct_id: int | None = None
    rule_code: str | None = None
    rule_type: str = "OPTION_SCORE_MAP"
    parameters: dict = Field(default_factory=dict)
    formula_expression: str | None = None
    source_reference: str | None = None
    rule_version: str | None = None
    status: str = "DRAFT"


class ScoringRuleRead(BaseModel):
    id: int
    public_id: uuid.UUID
    instrument_version_id: int
    question_id: int | None
    construct_id: int | None
    rule_code: str | None
    rule_type: str
    parameters: dict
    status: str

    model_config = ConfigDict(from_attributes=True)


class BaremCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    population_label: str | None = None
    source_reference: str | None = None
    barem_version: str | None = None
    status: str = "DRAFT"
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None
    metadata: dict = Field(default_factory=dict)


class BaremRead(BaseModel):
    id: int
    public_id: uuid.UUID
    instrument_version_id: int
    name: str
    population_label: str | None
    source_reference: str | None
    status: str
    barem_version: str | None
    metadata: dict = metadata_field()
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BaremBandInput(BaseModel):
    construct_id: int
    code: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    min_value: float = Field(ge=0, le=100)
    max_value: float = Field(ge=0, le=100)
    severity_order: int = Field(ge=1)
    interpretation: str | None = None
    color_hint: str | None = None
    classification_code: str | None = None
    metadata: dict = Field(default_factory=dict)


class BaremBandRead(BaremBandInput):
    id: int
    barem_id: int
    metadata: dict = metadata_field()

    model_config = ConfigDict(from_attributes=True)


class BaremBandsReplace(BaseModel):
    bands: list[BaremBandInput] = Field(min_length=1)


class BaremBandGenerate(BaseModel):
    construct_ids: list[int] | None = None
    levels: Literal[3, 5] = 3
    labels: list[str] | None = None
    direction: Direction
    method: Literal["EQUAL_INTERVAL", "QUANTILES"] = "EQUAL_INTERVAL"
    study_id: int | None = None


class BaremEditableCopyCreate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    barem_version: str | None = Field(default=None, max_length=100)


class BaremDetailRead(BaremRead):
    bands: list[BaremBandRead] = Field(default_factory=list)


class BaremActivationRead(BaseModel):
    id: int
    status: str
    activated: bool
    validations: list[str] = Field(default_factory=list)


class BaremCutoffCreate(BaseModel):
    construct_id: int
    cut_1: float = Field(ge=0, le=100)
    cut_2: float = Field(ge=0, le=100)
    direction: Direction = "HIGHER_BETTER"
    favorable_label: str = "FAVORABLE"
    intermediate_label: str = "INTERMEDIO"
    unfavorable_label: str = "DESFAVORABLE"


class BaremCutoffRead(BaseModel):
    id: int
    barem_id: int
    construct_id: int
    cut_1: float
    cut_2: float
    direction: str | None
    favorable_label: str
    intermediate_label: str
    unfavorable_label: str

    model_config = ConfigDict(from_attributes=True)


class ConstructResultRead(BaseModel):
    """Resultado por constructo, con supresión de privacidad ya aplicada (§31).

    El frontend nunca debe inferir favorable/intermedio/desfavorable leyendo
    texto de labels — estos campos ya vienen resueltos por el backend.
    """

    construct_id: int
    construct_code: str
    construct_name: str
    construct_type: str
    n_valid: int
    suppressed: bool
    suppression_reason: str | None = None
    favorable_n: int | None
    intermediate_n: int | None
    unfavorable_n: int | None
    favorable_pct: float | None
    intermediate_pct: float | None
    unfavorable_pct: float | None
    construct_score: float | None
    classification_status: str
    collective_classification: str | None
    priority_rank: int | None = None
    barem_id: int | None = None
    barem_status: str | None = None
    official_equivalence: bool = False


class CensopasResultsResponse(BaseModel):
    study_id: int
    analysis_run_id: int | None = None
    scoring_status: str
    official_equivalence_enabled: bool
    results: list[ConstructResultRead]


class CensopasPlanRead(BaseModel):
    """Catálogo de 'planes' (alias de negocio sobre `InstrumentVersion` oficiales,
    `is_system=True`, `status` publicado). Solo expone versiones ya activadas —
    nunca `DRAFT`/`TEST` — para que el selector de la empresa jamás ofrezca una
    versión en construcción."""

    instrument_id: int
    instrument_version_id: int
    version_kind: Literal["SHORT", "MEDIUM"]
    version_code: str
    status: str
    plan_label: str
    plan_description: str
    question_count: int
    scored_item_count: int
    dimension_count: int
    subdimension_count: int
    ready_for_scoring: bool


class CensopasPlansResponse(BaseModel):
    plans: list[CensopasPlanRead] = Field(default_factory=list)


class CensopasInstrumentCatalogRead(BaseModel):
    code: str
    name: str
    questions: int
    psychosocial_questions: int
    dimensions: int
    subdimensions: int
    recommended_population: str


class AnalyticsToolCatalogRead(BaseModel):
    code: str
    name: str
    category: str
    description: str | None = None


class AnalyticsPlanCatalogRead(BaseModel):
    code: str
    name: str
    description: str | None = None
    level: int
    tools: list[AnalyticsToolCatalogRead] = Field(default_factory=list)


class CensopasCatalogResponse(BaseModel):
    instrument_versions: list[CensopasInstrumentCatalogRead] = Field(default_factory=list)
    analytics_plans: list[AnalyticsPlanCatalogRead] = Field(default_factory=list)


class StudyAnalyticsToolsResponse(BaseModel):
    study_id: int
    plan_code: str
    plan_name: str
    tools: list[AnalyticsToolCatalogRead] = Field(default_factory=list)


class CensopasReadiness(BaseModel):
    instrument_version_id: int
    version_kind: Literal["SHORT", "MEDIUM", "UNKNOWN"]
    ready_for_scoring: bool
    ready_for_official_reporting: bool
    expected: dict[str, int]
    actual: dict[str, int]
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    is_censopas_instrument: bool = False

class CensopasManifestOption(BaseModel):
    raw_code: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1)
    numeric_value: float = Field(ge=1)
    sort_order: int | None = None


class CensopasManifestScale(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    options: list[CensopasManifestOption] = Field(min_length=2)


class CensopasManifestQuestion(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    source_code: str = Field(min_length=1, max_length=100)
    question_text: str = Field(min_length=1)
    question_type: Literal["LIKERT", "SINGLE_CHOICE", "MULTIPLE_CHOICE", "NUMBER", "TEXT", "BOOLEAN", "DATE", "DATETIME"]
    is_scored: bool
    research_role: Literal["EXOGENOUS", "ENDOGENOUS", "MEDIATOR", "MODERATOR", "CONTROL"] | None = None
    option_set_code: str | None = None
    is_required: bool = False
    sort_order: int
    category: str | None = None
    metadata: dict = Field(default_factory=dict)


class CensopasManifestItemLink(BaseModel):
    question_code: str = Field(min_length=1, max_length=100)
    weight: float = Field(default=1, gt=0)
    item_role: Literal["SCORED", "DESCRIPTIVE"] = "SCORED"
    scoring_direction: Literal["DIRECT", "REVERSE"] | None = None
    sort_order: int | None = None


class CensopasManifestConstruct(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    construct_type: Literal["VARIABLE", "DIMENSION", "SUBDIMENSION"]
    parent_code: str | None = None
    sort_order: int | None = None
    items: list[CensopasManifestItemLink] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class CensopasManifestScoringRule(BaseModel):
    question_code: str = Field(min_length=1, max_length=100)
    risk_map: dict[str, float]
    source_reference: str | None = None
    rule_version: str = Field(min_length=1, max_length=80)


class CensopasManifest(BaseModel):
    version_kind: Literal["SHORT", "MEDIUM"]
    manifest_version: str = Field(min_length=1, max_length=80)
    source_reference: str = Field(min_length=1)
    declared_hash: str | None = Field(default=None, min_length=64, max_length=64)
    scales: list[CensopasManifestScale] = Field(default_factory=list)
    questions: list[CensopasManifestQuestion] = Field(min_length=1)
    constructs: list[CensopasManifestConstruct] = Field(min_length=1)
    scoring_rules: list[CensopasManifestScoringRule] = Field(default_factory=list)


class CensopasManifestValidation(BaseModel):
    valid: bool
    calculated_hash: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    expected: dict[str, int]
    actual: dict[str, int]


class CensopasManifestImportRead(BaseModel):
    instrument_version_id: int
    manifest_hash: str
    imported: dict[str, int]
    readiness: CensopasReadiness

class CensopasUnitResultRead(ConstructResultRead):
    unit_type_id: int
    unit_type_code: str
    unit_type_name: str
    unit_id: int
    unit_code: str | None
    unit_name: str
    grouped_units: list[str] = Field(default_factory=list)


class CensopasUnitResultsResponse(BaseModel):
    study_id: int
    analysis_run_id: int | None = None
    unit_type_id: int
    min_publishable_n: int
    secondary_suppression_applied: bool
    results: list[CensopasUnitResultRead]


class CensopasBaremCutoffManifest(BaseModel):
    construct_code: str = Field(min_length=1, max_length=80)
    cut_1: float = Field(ge=0, le=100)
    cut_2: float = Field(ge=0, le=100)
    direction: Direction = "LOWER_BETTER"
    favorable_label: str = "FAVORABLE"
    intermediate_label: str = "INTERMEDIO"
    unfavorable_label: str = "DESFAVORABLE"


class CensopasBaremManifest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    barem_type: Literal["OFFICIAL", "REFERENCE", "EXPLORATORY"]
    population_label: str = Field(min_length=1, max_length=255)
    source_reference: str = Field(min_length=1)
    barem_version: str = Field(min_length=1, max_length=100)
    authority: str | None = None
    declared_hash: str | None = Field(default=None, min_length=64, max_length=64)
    cutoffs: list[CensopasBaremCutoffManifest] = Field(min_length=1)


class CensopasBaremManifestValidation(BaseModel):
    valid: bool
    calculated_hash: str
    errors: list[str] = Field(default_factory=list)
    required_constructs: list[str]
    configured_constructs: list[str]


class CensopasBaremImportRead(BaseModel):
    barem_id: int
    status: str
    barem_type: str
    content_hash: str
    cutoffs_imported: int
