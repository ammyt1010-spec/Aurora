"""Enlaces de distribución para baterías: nunca saltan tokens o privacidad por estudio."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.exceptions import (
    AuthorizationError, NotFoundError, PublicResourceUnavailableError, ValidationDomainError,
)
from app.core.security import get_current_user
from app.models.evaluation_bundle import EvaluationBundle
from app.models.instrument import InstrumentVersion
from app.models.project import Project
from app.models.study import Study
from app.models.user import OrganizationMembership, User
from app.services.audit_service import AuditService

router = APIRouter(tags=["evaluation-bundles"])


class BundleCreate(BaseModel):
    label: str = Field(min_length=3, max_length=180)
    study_ids: list[int] = Field(min_length=2, max_length=12)


class BundleRead(BaseModel):
    id: int
    public_id: UUID
    project_id: int
    label: str
    study_ids: list[int]
    status: str

    model_config = {"from_attributes": True}


class BundlePublicStudy(BaseModel):
    id: int
    name: str
    instrument_name: str
    survey_public_id: UUID


class BundlePublicRead(BaseModel):
    title: str
    evaluations: list[BundlePublicStudy]


def _is_open_for_public(study: Study) -> bool:
    if study.status != "OPEN" or study.requires_invitation:
        return False
    now = datetime.now(UTC)
    for boundary, is_start in ((study.start_at, True), (study.end_at, False)):
        if boundary is None:
            continue
        if boundary.tzinfo is None:
            boundary = boundary.replace(tzinfo=UTC)
        if is_start and now < boundary:
            return False
        if not is_start and now > boundary:
            return False
    return bool(study.public_id)


def _validate_studies(studies: list[Study], project_id: int, ids: list[int]) -> None:
    if len(ids) < 2 or len(ids) > 12 or len(set(ids)) != len(ids):
        raise ValidationDomainError("Selecciona entre 2 y 12 estudios diferentes.")
    by_id = {study.id: study for study in studies}
    if len(by_id) != len(ids) or any(id_ not in by_id for id_ in ids):
        raise ValidationDomainError("La batería contiene estudios inexistentes.")
    for study in studies:
        if study.project_id != project_id or not _is_open_for_public(study):
            raise ValidationDomainError(
                "Solo pueden agruparse estudios abiertos del proyecto con acceso público "
                "y sin invitaciones individuales. No se permite eludir tokens."
            )
        if study.instrument_version_id is None:
            raise ValidationDomainError("Cada evaluación debe tener una versión instrumental configurada.")


async def _require_admin(db: AsyncSession, project_id: int, user: User) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Proyecto no encontrado.")
    if project.organization_id is None:
        raise AuthorizationError("La batería requiere una empresa registrada.")
    membership = await db.get(OrganizationMembership, (project.organization_id, user.id))
    if membership is None or membership.role_code not in {"OWNER", "ADMIN"}:
        raise AuthorizationError("Solo el administrador de la empresa puede gestionar baterías.")
    return project


@router.post("/projects/{project_id}/bundles", response_model=BundleRead, status_code=201)
async def create_bundle(
    project_id: int,
    payload: BundleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _require_admin(db, project_id, user)
    ids = payload.study_ids
    studies = (await db.execute(select(Study).where(Study.id.in_(ids)))).scalars().all()
    _validate_studies(studies, project_id, ids)
    bundle = EvaluationBundle(
        project_id=project_id,
        organization_id=project.organization_id,
        created_by_user_id=user.id,
        label=payload.label.strip(),
        study_ids=list(ids),
        status="PUBLISHED",
    )
    db.add(bundle)
    await db.flush()
    await AuditService(db).log(
        action="EVALUATION_BUNDLE_PUBLISHED", entity_type="evaluation_bundle",
        entity_id=bundle.id, project_id=project_id,
        organization_id=project.organization_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(bundle)
    return BundleRead.model_validate(bundle)


@router.get("/projects/{project_id}/bundles", response_model=list[BundleRead])
async def list_bundles(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(db, project_id, user)
    rows = (await db.execute(
        select(EvaluationBundle).where(EvaluationBundle.project_id == project_id)
        .order_by(EvaluationBundle.created_at.desc(), EvaluationBundle.id.desc())
        .limit(100)
    )).scalars().all()
    return [BundleRead.model_validate(item) for item in rows]


@router.post("/projects/{project_id}/bundles/{bundle_id}/revoke", response_model=BundleRead)
async def revoke_bundle(
    project_id: int,
    bundle_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _require_admin(db, project_id, user)
    bundle = (await db.execute(
        select(EvaluationBundle).where(
            EvaluationBundle.id == bundle_id, EvaluationBundle.project_id == project_id
        ).with_for_update()
    )).scalar_one_or_none()
    if bundle is None:
        raise NotFoundError("Batería no encontrada.")
    if bundle.status != "REVOKED":
        bundle.status = "REVOKED"
        await AuditService(db).log(
            action="EVALUATION_BUNDLE_REVOKED", entity_type="evaluation_bundle",
            entity_id=bundle.id, project_id=project_id,
            organization_id=project.organization_id, user_id=user.id,
        )
    await db.commit()
    await db.refresh(bundle)
    return BundleRead.model_validate(bundle)


@router.get("/public/bundles/{public_id}", response_model=BundlePublicRead)
async def public_bundle(public_id: UUID, db: AsyncSession = Depends(get_db)):
    bundle = (await db.execute(
        select(EvaluationBundle).where(
            EvaluationBundle.public_id == public_id,
            EvaluationBundle.status == "PUBLISHED",
        )
    )).scalar_one_or_none()
    if bundle is None:
        raise PublicResourceUnavailableError("El enlace no está disponible.")
    studies = (await db.execute(
        select(Study).where(Study.id.in_(bundle.study_ids))
        .options(selectinload(Study.instrument_version).selectinload(InstrumentVersion.instrument))
    )).scalars().all()
    try:
        _validate_studies(studies, bundle.project_id, list(bundle.study_ids))
    except ValidationDomainError:
        raise PublicResourceUnavailableError("El enlace no está disponible.")
    by_id = {study.id: study for study in studies}
    return BundlePublicRead(
        title=bundle.label,
        evaluations=[
            BundlePublicStudy(
                id=study.id,
                name=study.name,
                instrument_name=study.instrument_name or "Evaluación corporativa",
                survey_public_id=study.public_id,
            )
            for id_ in bundle.study_ids if (study := by_id.get(id_)) is not None
        ],
    )
