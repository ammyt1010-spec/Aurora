from __future__ import annotations

from pydantic import BaseModel, Field


class ResponseDescriptivesSummary(BaseModel):
    included_cases: int
    question_count: int
    answered_cells: int
    missing_cells: int
    missing_pct: float


class ResponseFrequency(BaseModel):
    code: str
    label: str
    order: int
    n: int
    percentage: float
    cumulative_percentage: float | None = None


class NumericDescriptives(BaseModel):
    n_valid: int
    mean: float | None = None
    median: float | None = None
    mode: float | None = None
    std: float | None = None
    variance: float | None = None
    min: float | None = None
    max: float | None = None
    quartiles: list[float] | None = None


class ResponseQuestionDescriptives(BaseModel):
    question_id: int
    code: str
    question_text: str
    short_label: str | None = None
    category: str | None = None
    question_type: str
    is_scored: bool
    research_role: str | None
    measurement_level: str
    variable_id: int | None = None
    variable_code: str | None = None
    variable_label: str | None = None
    group_key: str
    group_label: str
    group_type: str
    valid_n: int
    missing_n: int
    suppressed: bool = False
    frequencies: list[ResponseFrequency] = Field(default_factory=list)
    numeric: NumericDescriptives | None = None


class ResponseDescriptivesGroup(BaseModel):
    key: str
    label: str
    group_type: str
    question_ids: list[int] = Field(default_factory=list)


class ResponseDescriptives(BaseModel):
    study_id: int
    instrument_version_id: int | None = None
    min_publishable_n: int
    summary: ResponseDescriptivesSummary
    groups: list[ResponseDescriptivesGroup] = Field(default_factory=list)
    questions: list[ResponseQuestionDescriptives] = Field(default_factory=list)
