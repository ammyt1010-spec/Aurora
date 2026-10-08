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


# Identificadores en payloads: todo objeto que se vincule a un estudio o
# proyecto debe pertenecer a esa misma frontera, aunque el autor tenga acceso
# a otras organizaciones.
_REFERENCE_MODEL = {
    "survey_id": Survey,
    "study_id": Study,
    "instrument_version_id": InstrumentVersion,
    "question_id": Question,
    "construct_id": Construct,
    "barem_id": Barem,
    "analysis_run_id": AnalysisRun,
    "variable_id": Variable,
    "action_plan_item_id": ActionPlanItem,
    "kpi_id": Kpi,
}
_REFERENCE_COLLECTION = {
    "variable_ids": "variable_id",
    "predictor_variable_ids": "variable_id",
    "construct_ids": "construct_id",
    "question_ids": "question_id",
}


async def validate_payload_references(
    db: AsyncSession,
    user: User,
    path_params: dict,
    payload: dict,
    *,
    url_path: str = "",
) -> None:
    """Prevent cross-tenant IDOR through IDs in JSON request bodies.

    This intentionally checks the full body, including batch operations. It
    is independent of the regular path-resource authorization.
    """
    scope_study = None
    scope_project = None
    if "study_id" in path_params:
        scope_study = await _get(db, Study, int(path_params["study_id"]))
        scope_project = scope_study.project_id
    elif "project_id" in path_params:
        scope_project = int(path_params["project_id"])
    elif "action_plan_id" in path_params:
        plan = await _get(db, ActionPlan, int(path_params["action_plan_id"]))
        scope_study = await _get(db, Study, plan.study_id)
        scope_project = scope_study.project_id
    elif "kpi_id" in path_params:
        kpi = await _get(db, Kpi, int(path_params["kpi_id"]))
        scope_study = await _get(db, Study, kpi.study_id)
        scope_project = scope_study.project_id

    async def check_ref(field: str, value: int) -> None:
        item = await _get(db, _REFERENCE_MODEL[field], value)
        target_project = None
        target_study = None
        target_version = None
        if field == "study_id":
            target_project, target_study = item.project_id, item.id
        elif field == "survey_id":
            target_project = item.project_id
        elif field == "instrument_version_id":
            target_version = item.id
            instrument = await _get(db, Instrument, item.instrument_id)
            target_project = instrument.project_id
            await _instrument(db, instrument.id, user, write=False)
        elif field == "question_id":
            target_version = item.instrument_version_id
            if target_version is not None:
                v = await _get(db, InstrumentVersion, target_version)
                instr = await _get(db, Instrument, v.instrument_id)
                target_project = instr.project_id
                await _instrument(db, instr.id, user, write=False)
            elif item.created_by_user_id != user.id:
                raise AuthorizationError("Pregunta de otro usuario.")
        elif field == "construct_id":
            target_version = item.instrument_version_id
            v = await _get(db, InstrumentVersion, target_version)
            instr = await _get(db, Instrument, v.instrument_id)
            target_project = instr.project_id
            await _instrument(db, instr.id, user, write=False)
        elif field == "barem_id":
            target_version = item.instrument_version_id
            v = await _get(db, InstrumentVersion, target_version)
            instr = await _get(db, Instrument, v.instrument_id)
            target_project = instr.project_id
            await _instrument(db, instr.id, user, write=False)
        elif field == "variable_id":
            target_project, target_study = item.project_id, item.study_id
        elif field == "analysis_run_id":
            target_study = item.study_id
            study = await _get(db, Study, target_study)
            target_project = study.project_id
        elif field == "action_plan_item_id":
            plan = await _get(db, ActionPlan, item.action_plan_id)
            target_study = plan.study_id
            study = await _get(db, Study, plan.study_id)
            target_project = study.project_id
        elif field == "kpi_id":
            target_study = item.study_id
            study = await _get(db, Study, target_study)
            target_project = study.project_id

        if scope_project is not None and target_project is not None and target_project != scope_project:
            raise AuthorizationError("La referencia pertenece a otro proyecto.")
        if scope_study is not None:
            if target_study is not None and target_study != scope_study.id:
                raise AuthorizationError("La referencia pertenece a otro estudio.")
            if target_version is not None and scope_study.instrument_version_id is not None:
                if target_version != scope_study.instrument_version_id:
                    raise AuthorizationError("La versión referenciada no pertenece a este estudio.")
        if target_project is not None:
            await _project(db, target_project, user, write=False)
        elif target_study is not None:
            await _study(db, target_study, user, write=False)

    async def walk(data: dict) -> None:
        for field, value in data.items():
            if value is None:
                continue
            if field in {"owner_user_id", "created_by_user_id", "requested_by_user_id"}:
                if int(value) != user.id:
                    raise AuthorizationError("No puedes asignar otro usuario como autor.")
            elif field in _REFERENCE_MODEL:
                await check_ref(field, int(value))
            elif field in _REFERENCE_COLLECTION and isinstance(value, list):
                for object_id in value:
                    await check_ref(_REFERENCE_COLLECTION[field], int(object_id))
            elif field == "items" and url_path.endswith("/variables/batch") and isinstance(value, list):
                for entry in value:
                    variable = await _get(db, Variable, int(entry["id"]))
                    if variable.project_id != scope_project:
                        raise AuthorizationError("Una variable del lote pertenece a otro proyecto.")
            # Campos JSON libres (settings, metadata, parameters) no son
            # relaciones arbitrarias: no deducir referencias por coincidencia.
    await walk(payload)

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

    if request.method.upper() in {"POST", "PUT", "PATCH"}:
        if "application/json" in request.headers.get("content-type", ""):
            payload = await request.json()
            if isinstance(payload, dict):
                await validate_payload_references(
                    db, user, p, payload, url_path=request.url.path
                )


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
