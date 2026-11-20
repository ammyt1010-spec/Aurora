from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthorizationError
from app.core.security import get_current_user
from app.models.billing import ReportOrder
from app.models.evaluation_entitlement import EvaluationEntitlement
from app.models.user import Organization, User
from app.schemas.organizations import OrganizationCreate
from app.schemas.projects import CensopasStudyConfig, ProjectCreate
from app.services.project_service import ProjectService
from app.services.study_service import StudyService
from app.services.billing_service import BillingService
from app.services.evaluation_access_service import EvaluationAccessService

router = APIRouter(tags=["quick-eval"])


class QuickEvalRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    company_ruc: str = Field(pattern=r"^\d{11}$")
    company_sector: str | None = Field(default=None, max_length=80)
    instrument_version: Literal["SHORT", "MEDIUM"]
    study_name: str = Field(min_length=1, max_length=255)
    population_invited: int = Field(ge=1, le=10_000_000)


class QuickEvalResponse(BaseModel):
    project_id: int
    study_id: int
    public_id: uuid.UUID
    survey_url: str | None
    payment_required: bool
    free_remaining: int
    order_id: int | None = None
    amount: str | None = None
    pricing_mode: str | None = None

    model_config = ConfigDict(from_attributes=True)


@router.post("/quick-eval", response_model=QuickEvalResponse, status_code=201)
async def create_quick_eval(
    payload: QuickEvalRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cuatro evaluaciones completas gratuitas; la siguiente espera pago."""
    access = EvaluationAccessService(session)
    await access.lock_account(current_user.id)
    trial = await access.trial_status(current_user.id)
    is_free = trial["remaining"] > 0
    tax_id_normalized = "".join(payload.company_ruc.split()).upper()
    existing_org = (
        await session.execute(
            select(Organization).where(Organization.tax_id == tax_id_normalized)
        )
    ).scalars().first()
    managed_company_id = current_user.managed_company_id or (current_user.metadata_ or {}).get("managed_company_id")
    if managed_company_id is not None and (existing_org is None or existing_org.id != managed_company_id):
        raise AuthorizationError("Esta cuenta solo puede evaluar la empresa para la que fue emitida.")

    project_payload = ProjectCreate(
        owner_user_id=current_user.id,
        name=payload.study_name,
        project_type="CENSO",
        censopas_study=CensopasStudyConfig(
            instrument_version=payload.instrument_version,
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

    try:
        project = await ProjectService(session).create(project_payload, commit=False)
        study_id = (project.metadata_ or {}).get("censopas_study_id")
        if not study_id:
            raise RuntimeError("No se encontró censopas_study_id en la metadata del proyecto")
        entitlement = EvaluationEntitlement(
            user_id=current_user.id,
            study_id=study_id,
            access_kind="FREE" if is_free else "PAID",
            status="ACTIVE" if is_free else "PENDING_PAYMENT",
        )
        session.add(entitlement)
        await session.flush()
        order = None
        if is_free:
            study = await StudyService(session).open(study_id, commit=False)
        else:
            study = await StudyService(session).get(study_id)
            method = "CENSOPAS_CORTA" if payload.instrument_version == "SHORT" else "CENSOPAS_MEDIA"
            order = await BillingService(session).create_quote(
                study_id, payload.population_invited, current_user,
                method_code=method, commit=False,
            )
            entitlement.order_id = order.id
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return QuickEvalResponse(
        project_id=project.id,
        study_id=study.id,
        public_id=study.public_id,
        survey_url=f"/encuesta/{study.public_id}" if is_free else None,
        payment_required=not is_free,
        free_remaining=trial["remaining"] - 1 if is_free else 0,
        order_id=order.id if order else None,
        amount=str(order.amount) if order and order.amount is not None else None,
        pricing_mode=order.pricing_mode if order else None,
    )


@router.get("/quick-eval/trial-status")
async def trial_status(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await EvaluationAccessService(session).trial_status(current_user.id)


@router.get("/quick-eval/studies/{study_id}/access")
async def evaluation_access(
    study_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await BillingService(session)._organization_admin(study_id, current_user)
    entitlement = await EvaluationAccessService(session).for_study(study_id)
    if entitlement is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("No existe un acceso comercial para esta evaluación.")
    study = await StudyService(session).get(study_id)
    order = await session.get(ReportOrder, entitlement.order_id) if entitlement.order_id else None
    return {
        "study_id": study_id,
        "access_kind": entitlement.access_kind,
        "status": entitlement.status,
        "survey_url": f"/encuesta/{study.public_id}" if entitlement.status == "ACTIVE" and study.status == "OPEN" else None,
        "order_id": order.id if order else None,
        "order_status": order.status if order else None,
        "amount": str(order.amount) if order and order.amount is not None else None,
        "currency": order.currency if order else "PEN",
        "free_report_id": entitlement.free_report_id,
    }
