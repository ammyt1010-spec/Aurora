from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.core.pagination import Page, PageParams, page_params
from app.schemas.datasets import DataDictionary, LongDataset, WideDataset
from app.schemas.invitations import (
    InvitationBatchRead,
    InvitationIssueRequest,
    InvitationRead,
    InvitationSummaryRead,
)
from app.schemas.studies import (
    StudyCreate,
    StudyRead,
    StudyUnitCreate,
    StudyUnitRead,
    StudyUnitTypeCreate,
    StudyUnitTypeRead,
    StudyUpdate,
)
from app.schemas.scoring import ScoreRunSummary, StudyResultsOverview
from app.services.dataset_service import DatasetService
from app.services.invitation_service import InvitationService
from app.services.study_service import StudyService
from app.services.scoring_orchestrator import run_canonical_scoring
from app.services.scoring_service import ScoringService

router = APIRouter(tags=["studies"])


@router.post("/projects/{project_id}/studies", response_model=StudyRead, status_code=201)
async def create_study(
    project_id: int, payload: StudyCreate, session: AsyncSession = Depends(get_db)
):
    service = StudyService(session)
    study = await service.create(project_id, payload)
    return StudyRead.model_validate(study)


@router.get("/projects/{project_id}/studies", response_model=Page[StudyRead])
async def list_studies(
    project_id: int,
    params: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_db),
):
    service = StudyService(session)
    return await service.list_by_project(project_id, params)


@router.get("/studies/{study_id}/unit-types", response_model=list[StudyUnitTypeRead])
async def list_study_unit_types(
    study_id: int, session: AsyncSession = Depends(get_db)
):
    items = await StudyService(session).list_unit_types(study_id)
    return [StudyUnitTypeRead.model_validate(item) for item in items]


@router.post(
    "/studies/{study_id}/unit-types",
    response_model=StudyUnitTypeRead,
    status_code=201,
)
async def create_study_unit_type(
    study_id: int,
    payload: StudyUnitTypeCreate,
    session: AsyncSession = Depends(get_db),
):
    item = await StudyService(session).create_unit_type(study_id, payload)
    return StudyUnitTypeRead.model_validate(item)


@router.get("/study-unit-types/{unit_type_id}/units", response_model=list[StudyUnitRead])
async def list_study_units(
    unit_type_id: int, session: AsyncSession = Depends(get_db)
):
    items = await StudyService(session).list_units(unit_type_id)
    return [StudyUnitRead.model_validate(item) for item in items]


@router.post(
    "/study-unit-types/{unit_type_id}/units",
    response_model=StudyUnitRead,
    status_code=201,
)
async def create_study_unit(
    unit_type_id: int,
    payload: StudyUnitCreate,
    session: AsyncSession = Depends(get_db),
):
    item = await StudyService(session).create_unit(unit_type_id, payload)
    return StudyUnitRead.model_validate(item)


@router.get("/studies/{study_id}", response_model=StudyRead)
async def get_study(study_id: int, session: AsyncSession = Depends(get_db)):
    service = StudyService(session)
    study = await service.get(study_id)
    return StudyRead.model_validate(study)


@router.patch("/studies/{study_id}", response_model=StudyRead)
async def update_study(
    study_id: int, payload: StudyUpdate, session: AsyncSession = Depends(get_db)
):
    service = StudyService(session)
    study = await service.update(study_id, payload)
    return StudyRead.model_validate(study)


@router.post("/studies/{study_id}/open", response_model=StudyRead)
async def open_study(study_id: int, session: AsyncSession = Depends(get_db)):
    service = StudyService(session)
    study = await service.open(study_id)
    return StudyRead.model_validate(study)


@router.post("/studies/{study_id}/close", response_model=StudyRead)
async def close_study(study_id: int, session: AsyncSession = Depends(get_db)):
    service = StudyService(session)
    study = await service.close(study_id)
    return StudyRead.model_validate(study)


@router.post("/studies/{study_id}/archive", response_model=StudyRead)
async def archive_study(study_id: int, session: AsyncSession = Depends(get_db)):
    service = StudyService(session)
    study = await service.archive(study_id)
    return StudyRead.model_validate(study)


# --- Scoring Likert y resultados baremados --------------------------------------


@router.post("/studies/{study_id}/scoring", response_model=ScoreRunSummary)
async def run_study_scoring(study_id: int, session: AsyncSession = Depends(get_db)):
    _run, summary = await run_canonical_scoring(session, study_id)
    return summary


@router.get(
    "/studies/{study_id}/results/overview", response_model=StudyResultsOverview
)
async def get_results_overview(study_id: int, session: AsyncSession = Depends(get_db)):
    return await ScoringService(session).get_overview(study_id)


@router.get(
    "/studies/{study_id}/results/baremos", response_model=StudyResultsOverview
)
async def get_barem_results(study_id: int, session: AsyncSession = Depends(get_db)):
    return await ScoringService(session).get_overview(study_id)


# --- Dataset (harness §19-20, §45) ------------------------------------------------


@router.get("/studies/{study_id}/data-dictionary", response_model=DataDictionary)
async def get_data_dictionary(study_id: int, session: AsyncSession = Depends(get_db)):
    service = DatasetService(session)
    return await service.load_variable_dictionary(study_id)


@router.get("/studies/{study_id}/dataset/long", response_model=LongDataset)
async def get_long_dataset(study_id: int, session: AsyncSession = Depends(get_db)):
    service = DatasetService(session)
    return await service.load_long_dataset(study_id)


@router.get("/studies/{study_id}/dataset/wide", response_model=WideDataset)
async def get_wide_dataset(study_id: int, session: AsyncSession = Depends(get_db)):
    service = DatasetService(session)
    return await service.load_wide_dataset(study_id)


# --- Invitaciones de un solo uso (E-17) --------------------------------------------


@router.post(
    "/studies/{study_id}/invitations", response_model=InvitationBatchRead, status_code=201
)
async def issue_invitations(
    study_id: int, payload: InvitationIssueRequest, session: AsyncSession = Depends(get_db)
):
    tokens = await InvitationService(session).issue(study_id, payload.count)
    return InvitationBatchRead(tokens=tokens)


@router.get(
    "/studies/{study_id}/invitations",
    response_model=InvitationSummaryRead,
    response_model_exclude_none=True,
)
async def get_invitations_summary(
    study_id: int,
    include_revoked: bool = False,
    session: AsyncSession = Depends(get_db),
):
    summary = await InvitationService(session).summary(study_id, include_revoked=include_revoked)
    return InvitationSummaryRead(**summary)


@router.get("/studies/{study_id}/invitations/list", response_model=list[InvitationRead])
async def list_study_invitations(
    study_id: int, status: str | None = None, session: AsyncSession = Depends(get_db)
):
    items = await InvitationService(session).list_invitations(study_id, status)
    return [InvitationRead.model_validate(item) for item in items]


@router.post(
    "/studies/{study_id}/invitations/{invitation_id}/revoke", response_model=InvitationRead
)
async def revoke_study_invitation(
    study_id: int,
    invitation_id: int,
    reason: str | None = None,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invitation = await InvitationService(session).revoke(
        study_id, invitation_id, reason, user_id=user.id
    )
    return InvitationRead.model_validate(invitation)
