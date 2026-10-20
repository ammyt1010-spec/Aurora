from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ConflictError
from app.core.security import get_current_user
from app.models.user import Organization, User
from app.schemas.organizations import OrganizationCreate
from app.schemas.projects import CensopasStudyConfig, ProjectCreate
from app.services.project_service import ProjectService
from app.services.study_service import StudyService

router = APIRouter(tags=["quick-eval"])


class QuickEvalRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    company_ruc: str = Field(min_length=3, max_length=80)
    company_sector: str | None = Field(default=None, max_length=80)
    instrument_version: Literal["SHORT", "MEDIUM"]
    study_name: str = Field(min_length=1, max_length=255)
    population_invited: int | None = Field(default=None, ge=1)


class QuickEvalResponse(BaseModel):
    project_id: int
    study_id: int
    public_id: uuid.UUID
    survey_url: str
    plan_code: str = "PREMIUM"
    free_report: bool = True
    free_reports_remaining: int = 0

    model_config = ConfigDict(from_attributes=True)


@router.post("/quick-eval", response_model=QuickEvalResponse, status_code=201)
async def create_quick_eval(
    payload: QuickEvalRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crea una evaluación rápida (organización, proyecto CENSO, estudio) en un solo paso."""
    tax_id_normalized = "".join(payload.company_ruc.split()).upper()
    existing_org = (
        await session.execute(
            select(Organization)
            .where(Organization.tax_id == tax_id_normalized)
            .with_for_update()
        )
    ).scalars().first()

    if existing_org and existing_org.free_report_claimed_at is not None:
        raise ConflictError(
            "Esta empresa ya utilizó su informe gratuito de Aurora. Puedes continuar con un plan corporativo a medida.",
            free_report_claimed=True,
            project_id=existing_org.free_report_project_id,
        )

    project_payload = ProjectCreate(
        owner_user_id=current_user.id,
        name=payload.study_name,
        project_type="CENSO",
        metadata={
            "commercial_tier": "FREE_REPORT",
            "free_report": True,
            "included_capabilities": [
                "anonymous_survey",
                "live_telemetry",
                "premium_analytics",
                "sunafil_report",
            ],
        },
        censopas_study=CensopasStudyConfig(
            instrument_version=payload.instrument_version,
            analytics_plan="PREMIUM",
            workplace_name=payload.company_name,
            population_invited=payload.population_invited,
        ),
    )

    if existing_org:
        project_payload.organization_id = existing_org.id
    else:
        project_payload.new_organization = OrganizationCreate(
            name=payload.company_name,
            tax_id=payload.company_ruc,
            organization_type=payload.company_sector,
        )

    project_service = ProjectService(session)
    try:
        project = await project_service.create(project_payload, claim_free_report=True)
    except IntegrityError as exc:
        raise ConflictError(
            "La empresa ya está registrada o su informe gratuito ya fue utilizado.",
            free_report_claimed=True,
        ) from exc

    study_id = project.metadata_.get("censopas_study_id")
    if not study_id:
        raise RuntimeError("No se encontró censopas_study_id en la metadata del proyecto")

    study_service = StudyService(session)
    study = await study_service.open(study_id)

    survey_url = f"/s/{study.public_id}"

    return QuickEvalResponse(
        project_id=project.id,
        study_id=study.id,
        public_id=study.public_id,
        survey_url=survey_url,
        plan_code="PREMIUM",
        free_report=True,
        free_reports_remaining=0,
    )
