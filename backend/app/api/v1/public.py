from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.participant_tokens import create_participant_token
from app.core.rate_limit import enforce_public_session_rate_limit
from app.schemas.public import (
    PublicResponseSessionCreate,
    PublicResponseSessionRead,
    PublicSurveyBundle,
)
from app.services.public_survey_service import PublicSurveyService

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/studies/{public_id}", response_model=PublicSurveyBundle)
async def get_public_study(public_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    service = PublicSurveyService(session)
    return await service.get_open_study_bundle(public_id)


@router.post(
    "/studies/{public_id}/response-sessions",
    response_model=PublicResponseSessionRead,
    status_code=201,
)
async def create_public_response_session(
    public_id: uuid.UUID,
    payload: PublicResponseSessionCreate | None = Body(default=None),
    session: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(enforce_public_session_rate_limit),
):
    service = PublicSurveyService(session)
    invitation_token = payload.invitation_token if payload else None
    response_session = await service.create_session_for_public_study(public_id, invitation_token)
    return PublicResponseSessionRead.model_validate(response_session).model_copy(
        update={"access_token": create_participant_token(response_session.id)}
    )
