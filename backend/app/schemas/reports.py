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
    report_type: str
    instrument_version_id: int | None = None
    template_config: dict = Field(default_factory=dict)


class ReportTemplateRead(BaseModel):
    id: int
    public_id: uuid.UUID
    code: str | None
    name: str
    report_type: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class ReportRunCreate(BaseModel):
    report_template_id: int | None = None
    analysis_run_id: int | None = None
    output_format: OutputFormat = "DOCX"
    requested_by_user_id: int | None = None
    report_mode: Literal["PROVISIONAL", "OFFICIAL"] = "PROVISIONAL"
    sections: list[str] = Field(default_factory=list)


class ReportPreviewRead(BaseModel):
    preview_id: int
    status: str
    pages: int | None
    preview_url: str


class ReportRunRead(BaseModel):
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
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
