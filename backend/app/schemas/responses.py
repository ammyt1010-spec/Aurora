from __future__ import annotations

import datetime as dt
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import metadata_field


class ResponseSessionRead(BaseModel):
    id: int
    public_id: uuid.UUID
    study_id: int
    anonymous_token: uuid.UUID
    status: str
    validation_status: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: int | None
    completion_pct: float | None
    exclusion_reason: str | None
    metadata: dict = metadata_field()

    model_config = ConfigDict(from_attributes=True)


class ResponseUpsert(BaseModel):
    """Body genérico de respuesta (harness §17): sólo uno de estos valores debe venir."""

    raw_code: str | None = None
    numeric_value: float | None = None
    text_value: str | None = None
    boolean_value: bool | None = None
    date_value: dt.date | None = None
    datetime_value: datetime | None = None
    option_id: int | None = None
    selected_option_ids: list[int] | None = None
    is_missing: bool = False

    @model_validator(mode="after")
    def _exactly_one_value(self) -> "ResponseUpsert":
        # raw_code y numeric_value cuentan como un solo "slot" combinado: el
        # servicio valida que sean consistentes entre sí contra el catálogo
        # de opciones (E-03) — aquí sólo se exige que no vengan junto a otro
        # tipo de valor distinto.
        slots = (
            self.raw_code is not None or self.numeric_value is not None,
            self.text_value is not None,
            self.boolean_value is not None,
            self.date_value is not None,
            self.datetime_value is not None,
            self.option_id is not None,
            self.selected_option_ids is not None,
        )
        supplied = sum(slots)

        if self.is_missing and supplied:
            raise ValueError("Una respuesta ausente no puede incluir un valor")
        if not self.is_missing and supplied != 1:
            raise ValueError(
                "Debe enviarse exactamente un valor (raw_code y numeric_value pueden "
                "combinarse) o marcar is_missing=true"
            )
        if self.selected_option_ids is not None and not self.selected_option_ids:
            raise ValueError("selected_option_ids no puede ser una lista vacía")
        return self


class ResponseRead(BaseModel):
    id: int
    study_id: int
    response_session_id: int
    question_id: int
    option_id: int | None
    raw_code: str | None
    numeric_value: float | None
    text_value: str | None
    boolean_value: bool | None
    date_value: dt.date | None
    datetime_value: datetime | None
    is_missing: bool
    answered_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResponseSessionCompleteRequest(BaseModel):
    exclusion_reason: str | None = None


class ResponseSessionProgressRead(BaseModel):
    response_session_id: int
    study_id: int
    status: str
    validation_status: str | None = None
    total_questions: int
    answered_questions: int
    completion_pct: float
    is_completed: bool
    can_resume: bool
