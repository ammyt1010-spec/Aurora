from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.security import get_optional_current_user
from app.models.instrument import INSTRUMENT_DISCIPLINES, INSTRUMENT_STATUSES
from app.models.study import Study
from app.models.user import OrganizationMembership, User
from app.core.pagination import Page, PageParams, page_params
from app.schemas.instruments import (
    ConstructMatrix,
    InstrumentCreate,
    InstrumentRead,
    InstrumentStatusUpdateRequest,
    InstrumentTree,
    InstrumentUpdate,
    InstrumentVersionCloneRequest,
    InstrumentVersionCreate,
    InstrumentVersionRead,
    InstrumentVersionUpdate,
    MethodologicalValidationResult,
)
from app.schemas.questions import (
    OptionSetCreate,
    OptionSetRead,
    OptionSetUpdate,
    QuestionBatchUpdate,
    QuestionCreate,
    QuestionRead,
    QuestionUpdate,
)
from app.services.instrument_service import InstrumentService
from app.services.question_service import QuestionService

router = APIRouter(tags=["instruments"])


async def _resolve_user_org_id(session: AsyncSession, user: User | None, explicit_org_id: int | None = None) -> int | None:
    if explicit_org_id is not None:
        return explicit_org_id
    if user is None:
        return None
    stmt = select(OrganizationMembership.organization_id).where(OrganizationMembership.user_id == user.id).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


# --- Catálogo multidisciplinario y disciplinas ----------------------------------


@router.get("/instruments/disciplines")
async def list_disciplines():
    """Catálogo oficial de disciplinas metodológicas soportadas por AURORA."""
    labels = {
        "PSICOSOCIAL": "Riesgos Psicosociales (CENSOPAS / SUSESO / ISTAS21)",
        "ERGONOMIA": "Ergonomía y Factores Físicos (ROSA, RULA, REBA)",
        "CLIMA_ORGANIZACIONAL": "Clima Organizacional y Cultura",
        "SEGURIDAD_SALUD": "Seguridad y Salud en el Trabajo (NOSACQ-50)",
        "LIDERAZGO_BURNOUT": "Liderazgo, Engagement y Burnout (MBI)",
        "OTRO": "Otras Escalas Corporativas",
    }
    return [
        {"code": code, "name": labels.get(code, code.replace("_", " ").title())}
        for code in INSTRUMENT_DISCIPLINES
    ]


# --- Instruments ---------------------------------------------------------------


@router.post("/instruments", response_model=InstrumentRead, status_code=201)
async def create_instrument(
    payload: InstrumentCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = InstrumentService(session)
    user_org_id = await _resolve_user_org_id(session, current_user, payload.organization_id)
    safe_payload = payload if current_user is None else payload.model_copy(
        update={
            "owner_user_id": current_user.id,
            "project_id": payload.project_id,
            "organization_id": user_org_id,
            "is_system": payload.is_system if current_user.id == 1 else False,
        }
    )
    instrument = await service.create(safe_payload)
    return InstrumentRead.model_validate(instrument)


@router.post(
    "/projects/{project_id}/instruments", response_model=InstrumentRead, status_code=201
)
async def create_project_instrument(
    project_id: int,
    payload: InstrumentCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = InstrumentService(session)
    user_org_id = await _resolve_user_org_id(session, current_user, payload.organization_id)
    safe_payload = payload if current_user is None else payload.model_copy(
        update={"owner_user_id": current_user.id, "project_id": project_id, "organization_id": user_org_id, "is_system": False}
    )
    instrument = await service.create(safe_payload, project_id=project_id)
    return InstrumentRead.model_validate(instrument)


@router.get("/instruments", response_model=Page[InstrumentRead])
async def list_instruments(
    discipline: str | None = Query(None, description="Filtrar por disciplina metodológica"),
    status: str | None = Query(None, description="Filtrar por estado del instrumento"),
    query: str | None = Query(None, description="Buscar por nombre, código o autor"),
    organization_id: int | None = Query(None, description="Id de organización para aislamiento multiempresa"),
    params: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = InstrumentService(session)
    user_org_id = await _resolve_user_org_id(session, current_user, organization_id)
    return await service.list(
        params,
        owner_user_id=current_user.id if current_user else None,
        organization_id=user_org_id,
        discipline=discipline,
        status=status,
        search_query=query,
    )


@router.get("/projects/{project_id}/instruments", response_model=Page[InstrumentRead])
async def list_project_instruments(
    project_id: int,
    discipline: str | None = Query(None),
    status: str | None = Query(None),
    query: str | None = Query(None),
    params: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_db),
):
    service = InstrumentService(session)
    return await service.list(
        params, project_id=project_id, discipline=discipline, status=status, search_query=query
    )


@router.get("/instruments/{instrument_id}", response_model=InstrumentRead)
async def get_instrument(
    instrument_id: int,
    organization_id: int | None = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = InstrumentService(session)
    user_org_id = await _resolve_user_org_id(session, current_user, organization_id)
    instrument = await service.get(instrument_id, organization_id=user_org_id)
    return InstrumentRead.model_validate(instrument)


@router.patch("/instruments/{instrument_id}", response_model=InstrumentRead)
async def update_instrument(
    instrument_id: int,
    payload: InstrumentUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = InstrumentService(session)
    user_org_id = await _resolve_user_org_id(session, current_user)
    instrument = await service.update_instrument(instrument_id, payload, organization_id=user_org_id)
    return InstrumentRead.model_validate(instrument)


@router.post("/instruments/{instrument_id}/status", response_model=InstrumentRead)
async def update_instrument_status(
    instrument_id: int,
    payload: InstrumentStatusUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = InstrumentService(session)
    user_org_id = await _resolve_user_org_id(session, current_user)
    instrument = await service.update_status(
        instrument_id, payload.status, payload.notes, organization_id=user_org_id
    )
    return InstrumentRead.model_validate(instrument)


# --- Asociación a Estudios -----------------------------------------------------


@router.post("/studies/{study_id}/instruments/{version_id}")
async def link_study_instrument(
    study_id: int,
    version_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Vincula una versión de instrumento a un estudio empresarial."""
    study = await session.get(Study, study_id)
    if study is None:
        raise NotFoundError("Estudio no encontrado")
    service = InstrumentService(session)
    version = await service.get_version(version_id)
    study.instrument_version_id = version.id
    await session.commit()
    return {
        "status": "success",
        "study_id": study_id,
        "instrument_version_id": version.id,
        "version_code": version.version_code,
    }


# --- Versions --------------------------------------------------------------------


@router.post(
    "/instruments/{instrument_id}/versions",
    response_model=InstrumentVersionRead,
    status_code=201,
)
async def create_instrument_version(
    instrument_id: int,
    payload: InstrumentVersionCreate,
    session: AsyncSession = Depends(get_db),
):
    service = InstrumentService(session)
    version = await service.create_version(instrument_id, payload)
    return InstrumentVersionRead.model_validate(version)


@router.get(
    "/instruments/{instrument_id}/versions", response_model=list[InstrumentVersionRead]
)
async def list_instrument_versions(instrument_id: int, session: AsyncSession = Depends(get_db)):
    service = InstrumentService(session)
    versions = await service.list_versions(instrument_id)
    return [InstrumentVersionRead.model_validate(v) for v in versions]


@router.get(
    "/instruments/{instrument_id}/versions/{version_id}",
    response_model=InstrumentVersionRead,
)
async def get_instrument_version(
    instrument_id: int, version_id: int, session: AsyncSession = Depends(get_db)
):
    service = InstrumentService(session)
    version = await service.get_version(version_id)
    if version.instrument_id != instrument_id:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("La versión no pertenece al instrumento indicado")
    return InstrumentVersionRead.model_validate(version)


@router.patch("/instrument-versions/{version_id}", response_model=InstrumentVersionRead)
async def update_instrument_version(
    version_id: int, payload: InstrumentVersionUpdate, session: AsyncSession = Depends(get_db)
):
    service = InstrumentService(session)
    version = await service.update_version(version_id, payload)
    return InstrumentVersionRead.model_validate(version)


@router.post(
    "/instrument-versions/{version_id}/validate",
    response_model=MethodologicalValidationResult,
)
async def validate_instrument_version(
    version_id: int, session: AsyncSession = Depends(get_db)
):
    """Ejecuta la auditoría psicométrica y de baremos de una versión de instrumento."""
    service = InstrumentService(session)
    return await service.validate_version(version_id)


@router.post(
    "/instruments/{instrument_id}/versions/{version_id}/clone",
    response_model=InstrumentVersionRead,
    status_code=201,
)
async def clone_instrument_version(
    instrument_id: int,
    version_id: int,
    payload: InstrumentVersionCloneRequest,
    session: AsyncSession = Depends(get_db),
):
    service = InstrumentService(session)
    new_version = await service.clone_version(instrument_id, version_id, payload)
    return InstrumentVersionRead.model_validate(new_version)


# --- Árbol y matriz (§57, §58) ----------------------------------------------------


@router.get("/instrument-versions/{version_id}/tree", response_model=InstrumentTree)
async def get_instrument_tree(version_id: int, session: AsyncSession = Depends(get_db)):
    service = InstrumentService(session)
    return await service.get_tree(version_id)


@router.get(
    "/instrument-versions/{version_id}/construct-matrix", response_model=ConstructMatrix
)
async def get_construct_matrix(version_id: int, session: AsyncSession = Depends(get_db)):
    service = InstrumentService(session)
    return await service.get_matrix(version_id)


# --- Ítems / questions (harness §11) ----------------------------------------------


@router.get(
    "/instrument-versions/{version_id}/likert-scales", response_model=list[OptionSetRead]
)
async def list_likert_scales(version_id: int, session: AsyncSession = Depends(get_db)):
    service = QuestionService(session)
    scales = await service.list_likert_scales(version_id)
    return [OptionSetRead.model_validate(scale) for scale in scales]


@router.post(
    "/instrument-versions/{version_id}/likert-scales",
    response_model=OptionSetRead,
    status_code=201,
)
async def create_likert_scale(
    version_id: int, payload: OptionSetCreate, session: AsyncSession = Depends(get_db)
):
    service = QuestionService(session)
    scale = await service.create_likert_scale(version_id, payload)
    return OptionSetRead.model_validate(scale)


@router.patch("/option-sets/{option_set_id}", response_model=OptionSetRead)
async def update_likert_scale(
    option_set_id: int, payload: OptionSetUpdate, session: AsyncSession = Depends(get_db)
):
    service = QuestionService(session)
    scale = await service.update_likert_scale(option_set_id, payload)
    return OptionSetRead.model_validate(scale)


@router.get("/instrument-versions/{version_id}/items", response_model=list[QuestionRead])
async def list_items(version_id: int, session: AsyncSession = Depends(get_db)):
    service = QuestionService(session)
    questions = await service.list_by_version(version_id)
    return [QuestionRead.model_validate(q) for q in questions]


@router.post(
    "/instrument-versions/{version_id}/items", response_model=QuestionRead, status_code=201
)
async def create_item(
    version_id: int, payload: QuestionCreate, session: AsyncSession = Depends(get_db)
):
    service = QuestionService(session)
    question = await service.create(version_id, payload)
    return QuestionRead.model_validate(question)


@router.patch(
    "/instrument-versions/{version_id}/items/batch", response_model=list[QuestionRead]
)
async def batch_update_items(
    version_id: int, payload: QuestionBatchUpdate, session: AsyncSession = Depends(get_db)
):
    service = QuestionService(session)
    questions = await service.batch_update(version_id, payload)
    return [QuestionRead.model_validate(q) for q in questions]


@router.get("/items/{item_id}", response_model=QuestionRead)
async def get_item(item_id: int, session: AsyncSession = Depends(get_db)):
    service = QuestionService(session)
    question = await service.get(item_id)
    return QuestionRead.model_validate(question)


@router.patch("/items/{item_id}", response_model=QuestionRead)
async def update_item(
    item_id: int, payload: QuestionUpdate, session: AsyncSession = Depends(get_db)
):
    service = QuestionService(session)
    question = await service.update(item_id, payload)
    return QuestionRead.model_validate(question)


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: int, session: AsyncSession = Depends(get_db)):
    service = QuestionService(session)
    await service.delete(item_id)
