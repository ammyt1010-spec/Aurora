from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# DOCX (Word, con tablas de baremación + gráficas embebidas) es el formato
# por defecto — ver report_docx.py. JSON se conserva como salida "cruda"
# del mismo bundle, útil para integraciones (Power BI, etc.).
OutputFormat = Literal["JSON", "DOCX", "PDF"]


class ReportTemplateCreate(BaseModel):
    code: str | None = None
    name: str = Field(min_length=1, max_length=255)
    report_type: str = "EXECUTIVE"
    discipline: str = "PSICOSOCIAL"
    instrument_version_id: int | None = None
    template_config: dict = Field(default_factory=dict)


class ReportTemplateUpdate(BaseModel):
    name: str | None = None
    report_type: str | None = None
    discipline: str | None = None
    template_config: dict | None = None
    status: str | None = None


class ReportTemplateRead(BaseModel):
    id: int
    public_id: uuid.UUID
    code: str | None
    name: str
    report_type: str
    discipline: str = "PSICOSOCIAL"
    instrument_version_id: int | None = None
    template_config: dict = Field(default_factory=dict)
    is_system: bool = False
    status: str

    model_config = ConfigDict(from_attributes=True)


class ReportRunCreate(BaseModel):
    billing_order_id: int | None = Field(default=None, gt=0)
    report_template_id: int | None = None
    analysis_run_id: int | None = None
    output_format: OutputFormat = "DOCX"
    requested_by_user_id: int | None = None
    report_mode: Literal["PROVISIONAL", "OFFICIAL", "SAMPLE"] = "PROVISIONAL"
    is_sample_preview: bool = False
    sections: list[str] = Field(default_factory=list)


class ReportPreviewRead(BaseModel):
    preview_id: int
    status: str
    pages: int | None
    preview_url: str
    is_sample: bool = False
    watermark: str | None = None


class ReportRunRead(BaseModel):
    billing_order_id: int | None = None
    id: int
    public_id: uuid.UUID
    study_id: int
    report_template_id: int | None
    analysis_run_id: int | None
    status: str
    output_format: str
    storage_path: str | None = Field(default=None, exclude=True)
    data_hash: str | None
    generated_at: datetime | None
    error_message: str | None
    metadata_: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConstructExecutiveRanking(BaseModel):
    construct_code: str
    construct_name: str
    construct_type: str
    score_0_100: float | None = None
    level_label: str | None = None
    traffic_light: Literal["GREEN", "AMBER", "RED", "GRAY"]
    unfavorable_pct: float | None = None
    recommendation: str
    severity_order: int = 99


class ExecutiveDashboardResponse(BaseModel):
    study_id: int
    study_name: str
    company_name: str | None = None
    company_tax_id: str | None = None
    discipline: str = "PSICOSOCIAL"
    instrument_name: str
    period_start: str | None = None
    period_end: str | None = None
    participation: dict
    risk_distribution: dict
    construct_rankings: list[ConstructExecutiveRanking] = Field(default_factory=list)
    action_plans_summary: dict
    headline: str
    generated_at: str
    signature_hash: str


class ReportHistoryItemRead(BaseModel):
    id: int
    public_id: uuid.UUID
    study_id: int
    study_name: str
    discipline: str
    template_name: str | None = None
    output_format: str
    status: str
    data_hash: str | None = None
    generated_at: datetime | None = None
    requested_by_email: str | None = None
    requested_by_name: str | None = None
    billing_order_id: int | None = None
    billing_order_code: str | None = None
    download_count: int = 0
    is_sample_preview: bool = False
    created_at: datetime


class ReportAuditDetailRead(BaseModel):
    report_id: int
    public_id: uuid.UUID
    data_hash: str
    study_id: int
    study_name: str
    organization_name: str | None = None
    discipline: str
    template_name: str | None = None
    template_version: str | None = None
    emitted_by_user: str | None = None
    generated_at: datetime | None = None
    billing_order_id: int | None = None
    billing_order_status: str | None = None
    integrity_verified: bool = True
    access_logs_count: int = 0

