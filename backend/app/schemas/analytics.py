from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PercentageMode = Literal["COUNT", "ROW_PERCENT", "COLUMN_PERCENT", "TOTAL_PERCENT"]


class AnalysisMethodRead(BaseModel):
    id: int
    code: str
    name: str
    category: str | None
    engine: str
    enabled: bool

    model_config = ConfigDict(from_attributes=True)


class AvailableMethodsRequest(BaseModel):
    variable_ids: list[int] = Field(min_length=1)


class AvailableMethodsResponse(BaseModel):
    methods: list[str]


class DescribeRequest(BaseModel):
    variable_ids: list[int] = Field(min_length=1)


class FrequenciesRequest(BaseModel):
    variable_ids: list[int] = Field(min_length=1)


class CrosstabRequest(BaseModel):
    row_variable_id: int
    column_variable_id: int
    percentage_mode: PercentageMode = "COUNT"


class ChiSquareRequest(BaseModel):
    row_variable_id: int
    column_variable_id: int


class CompareGroupsRequest(BaseModel):
    dependent_variable_id: int
    group_variable_id: int


class CorrelationRequest(BaseModel):
    variable_x_id: int
    variable_y_id: int


ReliabilityMethod = Literal["CRONBACH_ALPHA", "MCDONALD_OMEGA"]


class ReliabilityRequest(BaseModel):
    construct_id: int
    methods: list[ReliabilityMethod] = Field(default_factory=lambda: ["CRONBACH_ALPHA", "MCDONALD_OMEGA"])


class LogisticRegressionRequest(BaseModel):
    """Regresión logística (Fase 9). Predictores numéricos únicamente en esta
    fase — no se codifican variables categóricas como dummies todavía."""

    outcome_variable_id: int
    predictor_variable_ids: list[int] = Field(min_length=1)


class KMeansRequest(BaseModel):
    variable_ids: list[int] = Field(min_length=1)
    k: int = Field(default=2, ge=2, le=10)


class NormalityRequest(BaseModel):
    construct_ids: list[int] | None = None
    histogram_bins: int = Field(default=10, ge=5, le=50)


class HistogramBin(BaseModel):
    min_value: float
    max_value: float
    n: int


class NormalityResultRead(BaseModel):
    construct_id: int
    construct_code: str
    construct_name: str
    n: int
    test: str | None
    statistic: float | None
    p_value: float | None
    status: str
    mean: float | None
    median: float | None
    standard_deviation: float | None
    minimum: float | None
    maximum: float | None
    histogram: list[HistogramBin] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class NormalityResponse(BaseModel):
    analysis_run_id: int
    study_id: int
    note: str
    results: list[NormalityResultRead]


class SpearmanMatrixRequest(BaseModel):
    construct_ids: list[int] | None = None
    exogenous_variable_ids: list[int] = Field(default_factory=list)
    # E-09: default seguro (opt-in). Requiere autenticación + rol elevado
    # sobre el proyecto del estudio — ver AdvancedAnalysisService.run_spearman_matrix.
    include_points: bool = False


class SpearmanVariableRead(BaseModel):
    key: str
    source_type: str
    source_id: int
    code: str
    label: str
    measurement_level: str


class SpearmanPointBin(BaseModel):
    """Celda agregada de una grilla x/y (E-09): nunca coordenadas individuales."""

    x_bin_center: float
    y_bin_center: float
    n: int


class SpearmanCellRead(BaseModel):
    x_key: str
    y_key: str
    rho: float | None
    p_value: float | None
    adjusted_p_value: float | None
    n: int
    magnitude: str | None
    significant: bool
    points_binned: list[SpearmanPointBin] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SpearmanMatrixResponse(BaseModel):
    analysis_run_id: int
    study_id: int
    method: str
    correction: str
    normality_required: bool
    variables: list[SpearmanVariableRead]
    cells: list[SpearmanCellRead]
    excluded: list[str] = Field(default_factory=list)


class ConstructCompareGroupsRequest(BaseModel):
    construct_id: int
    group_variable_id: int


class GroupSummaryRead(BaseModel):
    code: str
    n: int
    suppressed: bool
    mean: float | None
    median: float | None


class ConstructCompareGroupsResponse(BaseModel):
    analysis_run_id: int
    study_id: int
    construct_id: int
    group_variable_id: int
    method: str | None
    statistic: float | None
    p_value: float | None
    effect_size: float | None
    effect_label: str | None
    suppressed: bool
    groups: list[GroupSummaryRead]
    warnings: list[str] = Field(default_factory=list)


class AnalysisRunCreate(BaseModel):
    analysis_type: str
    parameters: dict = Field(default_factory=dict)
    requested_by_user_id: int | None = None


class AnalysisResultRead(BaseModel):
    id: int
    result_code: str | None
    result_type: str
    question_id: int | None
    construct_id: int | None
    n_valid: int | None
    numeric_value: float | None
    statistic_value: float | None
    p_value: float | None
    adjusted_p_value: float | None
    effect_size: float | None
    effect_label: str | None
    result_data: dict

    model_config = ConfigDict(from_attributes=True)


class AnalysisRunRead(BaseModel):
    id: int
    public_id: uuid.UUID
    study_id: int
    analysis_type: str
    engine: str
    parameters: dict
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime
    results: list[AnalysisResultRead] = []

    model_config = ConfigDict(from_attributes=True)


class LongitudinalPoint(BaseModel):
    study_id: int
    study_name: str
    study_status: str
    date: datetime | None = None
    n_valid: int
    mean_score: float | None = None
    median_score: float | None = None
    unfavorable_pct: float | None = None
    favorable_pct: float | None = None
    intermediate_pct: float | None = None
    suppressed: bool = False
    signature: str


class LongitudinalConstructTrend(BaseModel):
    construct_id: int
    construct_code: str
    construct_name: str
    construct_type: str
    points: list[LongitudinalPoint]
    is_comparable: bool
    delta_unfavorable_pct: float | None = None
    delta_mean_score: float | None = None
    trend_direction: str | None = None
    methodological_equivalence: bool = True
    incomparability_reasons: list[str] = Field(default_factory=list)


class LongitudinalComparisonResponse(BaseModel):
    project_id: int
    total_studies_analyzed: int
    reference_signature: str | None
    constructs: list[LongitudinalConstructTrend]
    methodological_notes: list[str] = Field(default_factory=list)
