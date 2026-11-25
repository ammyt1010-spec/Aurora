from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.organizations import (
    CollaboratorCodeCreate,
    CollaboratorCodeRead,
    JoinOrganizationRequest,
    JoinOrganizationResponse,
    OrganizationCreate,
    OrganizationMembershipRead,
    OrganizationRead,
)
from app.services.organization_service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationMembershipRead])
async def list_organizations(
    session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    rows = await OrganizationService(session).list_for_user(current_user.id)
    return [
        OrganizationMembershipRead(
            organization=OrganizationRead.model_validate(org),
            role_code=role,
            permissions=permissions or {},
            declared_workers=(org.metadata_ or {}).get("headcount"),
        )
        for org, role, permissions in rows
    ]


@router.post("", response_model=OrganizationRead, status_code=201)
async def create_organization(
    payload: OrganizationCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return OrganizationRead.model_validate(
        await OrganizationService(session).create(payload, current_user)
    )


@router.post("/join", response_model=JoinOrganizationResponse)
async def join_organization(
    payload: JoinOrganizationRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization = await OrganizationService(session).join(payload, current_user)
    return JoinOrganizationResponse(organization=OrganizationRead.model_validate(organization), role_code="COLLABORATOR")


@router.post("/{organization_id}/collaborator-codes", response_model=CollaboratorCodeRead, status_code=201)
async def create_collaborator_code(
    organization_id: int,
    payload: CollaboratorCodeCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code, raw_code = await OrganizationService(session).create_code(organization_id, payload, current_user)
    response = CollaboratorCodeRead.model_validate(code)
    response.code = raw_code
    return response


@router.get("/{organization_id}/collaborator-codes", response_model=list[CollaboratorCodeRead])
async def list_collaborator_codes(
    organization_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    codes = await OrganizationService(session).list_codes(organization_id, current_user)
    return [CollaboratorCodeRead.model_validate(code) for code in codes]


@router.post("/{organization_id}/collaborator-codes/{code_id}/revoke", response_model=CollaboratorCodeRead)
async def revoke_collaborator_code(
    organization_id: int,
    code_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code = await OrganizationService(session).revoke_code(organization_id, code_id, current_user)
    return CollaboratorCodeRead.model_validate(code)

