"""Project-scoped access checks for AURORA's private API routes.

Every private resource ID is resolved server-side to a project. Public survey
submission has its own narrowly scoped participant capability.
"""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError, NotFoundError
from app.core.security import get_current_user, get_optional_current_user
from app.core.participant_tokens import verify_participant_token
from app.models.analysis import AnalysisRun
from app.models.bsc import ActionPlan, ActionPlanItem, Kpi
from app.models.censopas import Barem
from app.models.construct import Construct
from app.models.export import Export
from app.models.instrument import Instrument, InstrumentVersion
from app.models.option_set import OptionSet
from app.models.project import Project
from app.models.question import Question
from app.models.report import ReportRun
from app.models.response import ResponseSession
from app.models.study import Study, StudyUnitType
from app.models.survey import Survey
from app.models.user import OrganizationMembership, User
from app.models.variable import Variable
from app.services.project_service import ProjectService


async def _get(db: AsyncSession, model: type, object_id: int):
    item = await db.get(model, object_id)
    if item is None:
        raise NotFoundError("Recurso no encontrado")
    return item


async def _project(db: AsyncSession, project_id: int, user: User, write: bool) -> None:
    item = await _get(db, Project, project_id)
    await ProjectService(db).ensure_access(item, user, write=write)


async def _study(db: AsyncSession, study_id: int, user: User, write: bool) -> None:
    item = await _get(db, Study, study_id)
    await _project(db, item.project_id, user, write)


async def _instrument(db: AsyncSession, instrument_id: int, user: User, write: bool) -> None:
    item = await _get(db, Instrument, instrument_id)
    if item.project_id is not None:
        await _project(db, item.project_id, user, write)
        return
    if item.is_system:
        if write:
            raise AuthorizationError("Los instrumentos del sistema son de solo lectura.")
        return
    if item.owner_user_id == user.id:
        return
    if item.organization_id is not None:
        membership = (await db.execute(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == item.organization_id,
            OrganizationMembership.user_id == user.id,
        ))).scalar_one_or_none()
        if membership is not None and (not write or membership.role_code in {"OWNER", "ADMIN"}):
            return
    raise AuthorizationError("No tienes acceso a este instrumento.")


async def _version(db: AsyncSession, version_id: int, user: User, write: bool) -> None:
    version = await _get(db, InstrumentVersion, version_id)
    await _instrument(db, version.instrument_id, user, write)


async def require_business_access(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Fail closed for unknown resource IDs; never trust ids in the request body."""
    p = request.path_params
    write = request.method.upper() not in {"GET", "HEAD", "OPTIONS"}
    if "study_id" in p:
        await _study(db, int(p["study_id"]), user, write)
    elif "project_id" in p:
        await _project(db, int(p["project_id"]), user, write)
    elif "report_id" in p:
        await _study(db, (await _get(db, ReportRun, int(p["report_id"]))).study_id, user, write)
    elif "export_id" in p:
        await _study(db, (await _get(db, Export, int(p["export_id"]))).study_id, user, write)
    elif "run_id" in p:
        await _study(db, (await _get(db, AnalysisRun, int(p["run_id"]))).study_id, user, write)
    elif "unit_type_id" in p:
        await _study(db, (await _get(db, StudyUnitType, int(p["unit_type_id"]))).study_id, user, write)
    elif "action_plan_id" in p:
        await _study(db, (await _get(db, ActionPlan, int(p["action_plan_id"]))).study_id, user, write)
    elif "kpi_id" in p:
        await _study(db, (await _get(db, Kpi, int(p["kpi_id"]))).study_id, user, write)
    elif "item_id" in p and request.url.path.find("/action-plan-items/") >= 0:
        action = await _get(db, ActionPlanItem, int(p["item_id"]))
        await _study(db, (await _get(db, ActionPlan, action.action_plan_id)).study_id, user, write)
    elif "survey_id" in p:
        await _project(db, (await _get(db, Survey, int(p["survey_id"]))).project_id, user, write)
    elif "variable_id" in p:
        await _project(db, (await _get(db, Variable, int(p["variable_id"]))).project_id, user, write)
    elif "version_id" in p:
        await _version(db, int(p["version_id"]), user, write)
    elif "instrument_id" in p:
        await _instrument(db, int(p["instrument_id"]), user, write)
    elif "construct_id" in p:
        await _version(db, (await _get(db, Construct, int(p["construct_id"]))).instrument_version_id, user, write)
    elif "barem_id" in p:
        await _version(db, (await _get(db, Barem, int(p["barem_id"]))).instrument_version_id, user, write)
    elif "option_set_id" in p:
        option = await _get(db, OptionSet, int(p["option_set_id"]))
        if option.instrument_version_id is not None:
            await _version(db, option.instrument_version_id, user, write)
        elif option.owner_user_id != user.id:
            raise AuthorizationError("No tienes acceso a esta escala.")
    elif "question_id" in p or "item_id" in p:
        question = await _get(db, Question, int(p.get("question_id", p.get("item_id"))))
        if question.instrument_version_id is not None:
            await _version(db, question.instrument_version_id, user, write)
        elif question.created_by_user_id != user.id:
            raise AuthorizationError("No tienes acceso a esta pregunta.")
    elif p:
        raise AuthorizationError("No hay política de acceso para este recurso.")


async def require_response_access(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
) -> None:
    """Only project members or the bearer of this specific survey session token."""
    p = request.path_params
    if "session_id" in p:
        response_session = await _get(db, ResponseSession, int(p["session_id"]))
        token = request.headers.get("X-Response-Token")
        if token:
            verify_participant_token(token, response_session.id)
            return
        if user is not None:
            await _study(db, response_session.study_id, user, write=True)
            return
        raise AuthenticationError("Falta un token válido de esta sesión.")
    if "study_id" in p and user is not None:
        await _study(db, int(p["study_id"]), user, write=True)
        return
    raise AuthenticationError("Debes iniciar sesión para crear sesiones internas.")
