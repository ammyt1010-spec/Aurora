from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_optional_current_user
from app.models.user import User
from app.core.pagination import Page, PageParams, page_params
from app.schemas.surveys import (
    SurveyCreate,
    SurveyFromInstrumentCreate,
    SurveyRead,
    SurveyUpdate,
)
from app.services.survey_service import SurveyService

router = APIRouter(tags=["surveys"])


@router.post("/projects/{project_id}/surveys", response_model=SurveyRead, status_code=201)
async def create_survey(
    project_id: int, payload: SurveyCreate, session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = SurveyService(session)
    safe = payload.model_copy(update={"created_by_user_id": current_user.id}) if current_user else payload
    survey = await service.create(project_id, safe)
    return SurveyRead.model_validate(survey)


@router.post(
    "/projects/{project_id}/surveys/from-instrument",
    response_model=SurveyRead,
    status_code=201,
)
async def create_survey_from_instrument(
    project_id: int, payload: SurveyFromInstrumentCreate, session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = SurveyService(session)
    safe = payload.model_copy(update={"created_by_user_id": current_user.id}) if current_user else payload
    survey = await service.create_from_instrument(project_id, safe)
    return SurveyRead.model_validate(survey)


@router.get("/projects/{project_id}/surveys", response_model=Page[SurveyRead])
async def list_surveys(
    project_id: int,
    params: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_db),
):
    service = SurveyService(session)
    return await service.list_by_project(project_id, params)


@router.get("/surveys/{survey_id}", response_model=SurveyRead)
async def get_survey(survey_id: int, session: AsyncSession = Depends(get_db)):
    service = SurveyService(session)
    survey = await service.get(survey_id)
    return SurveyRead.model_validate(survey)


@router.patch("/surveys/{survey_id}", response_model=SurveyRead)
async def update_survey(
    survey_id: int, payload: SurveyUpdate, session: AsyncSession = Depends(get_db)
):
    service = SurveyService(session)
    survey = await service.update(survey_id, payload)
    return SurveyRead.model_validate(survey)


@router.delete("/surveys/{survey_id}", status_code=204)
async def delete_survey(survey_id: int, session: AsyncSession = Depends(get_db)):
    service = SurveyService(session)
    await service.delete(survey_id)
