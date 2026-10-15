from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExportType = Literal["CSV", "XLSX", "SPSS", "POWERBI", "JSON", "PARQUET"]
DatasetShape = Literal["LONG", "WIDE", "AGGREGATED"]


class ExportCreate(BaseModel):
    export_type: ExportType
    dataset_shape: DatasetShape = "LONG"
    requested_by_user_id: int | None = None
    filters: dict = Field(default_factory=dict)


class ExportRead(BaseModel):
    id: int
    public_id: uuid.UUID
    study_id: int
    export_type: str
    dataset_shape: str
    status: str
    storage_path: str | None = Field(default=None, exclude=True)
    row_count: int | None
    generated_at: datetime | None
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
