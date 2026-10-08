from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.core.pagination import Page, PageParams, page_params
from app.schemas.instruments import (
    ConstructMatrix,
    InstrumentCreate,
    InstrumentRead,
    InstrumentTree,
    InstrumentVersionCloneRequest,
    InstrumentVersionCreate,
    InstrumentVersionRead,
    InstrumentVersionUpdate,
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


# --- Instruments ---------------------------------------------------------------


@router.post("/instruments", response_model=InstrumentRead, status_code=201)
async def create_instrument(payload: InstrumentCreate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = InstrumentService(session)
    safe_payload = payload.model_copy(update={"owner_user_id": current_user.id, "project_id": None, "organization_id": None, "is_system": False})
    instrument = await service.create(safe_payload)
    return InstrumentRead.model_validate(instrument)


@router.post(
    "/projects/{project_id}/instruments", response_model=InstrumentRead, status_code=201
)
async def create_project_instrument(
    project_id: int, payload: InstrumentCreate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    service = InstrumentService(session)
    safe_payload = payload.model_copy(update={"owner_user_id": current_user.id, "project_id": project_id, "is_system": False})
    instrument = await service.create(safe_payload, project_id=project_id)
    return InstrumentRead.model_validate(instrument)


@router.get("/instruments", response_model=Page[InstrumentRead])
async def list_instruments(
    params: PageParams = Depends(page_params), session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    service = InstrumentService(session)
    return await service.list(params, owner_user_id=current_user.id)


@router.get("/projects/{project_id}/instruments", response_model=Page[InstrumentRead])
async def list_project_instruments(
    project_id: int,
    params: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_db),
):
    service = InstrumentService(session)
    return await service.list(params, project_id=project_id)


@router.get("/instruments/{instrument_id}", response_model=InstrumentRead)
async def get_instrument(instrument_id: int, session: AsyncSession = Depends(get_db)):
    service = InstrumentService(session)
    instrument = await service.get(instrument_id)
    return InstrumentRead.model_validate(instrument)


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
