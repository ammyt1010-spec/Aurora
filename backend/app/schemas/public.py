from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class PublicOption(BaseModel):
    id: int
    raw_code: str
    label: str
    numeric_value: float | None = None
    sort_order: int | None = None

    model_config = ConfigDict(from_attributes=True)


class PublicQuestion(BaseModel):
    """Vista de una pregunta expuesta al encuestado anónimo — sin metadatos
    internos (scoring, construct links, created_by_user_id, etc.)."""

    id: int
    code: str | None
    question_text: str
    short_label: str | None
    question_type: str
    is_scored: bool
    research_role: str | None
    is_required: bool | None
    validation_rules: dict = Field(default_factory=dict)
    options: list[PublicOption] = Field(default_factory=list)


class PublicSection(BaseModel):
    id: int
    title: str | None
    description: str | None
    section_kind: str
    sort_order: int
    questions: list[PublicQuestion] = Field(default_factory=list)


class PublicSurveyBundle(BaseModel):
    """Todo lo que necesita el formulario público para renderizarse
    (harness §72-73: el frontend nunca calcula, sólo pinta lo que
    devuelve el backend)."""

    study_public_id: uuid.UUID
    requires_invitation: bool = False
    study_name: str
    survey_name: str
    survey_description: str | None
    questions: list[PublicQuestion]
    sections: list[PublicSection] = Field(default_factory=list)
    # Skin visual elegida en el paso "Formulario" del builder (ver
    # project.metadata["form_theme"] — a nivel de proyecto, no de survey,
    # para que sobreviva a que el proyecto recree su Survey/instrumento):
    # { style: "colmena" | "modernist", colors: { accent?, bg?, text? } }.
    # Vacío == skin "colmena" por defecto.
    theme: dict = Field(default_factory=dict)


class PublicResponseSessionCreate(BaseModel):
    """Body opcional del POST público (E-17): sólo se exige `invitation_token`
    cuando el estudio tiene `requires_invitation=True`."""

    invitation_token: str | None = None


class PublicResponseSessionRead(BaseModel):
    """Igual que ResponseSessionRead pero sólo con los campos que un
    respondiente anónimo necesita para continuar su sesión."""

    id: int
    public_id: uuid.UUID
    status: str
    completion_pct: float | None
    access_token: str = ""

    model_config = ConfigDict(from_attributes=True)
