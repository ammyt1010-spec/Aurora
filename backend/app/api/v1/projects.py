from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import Page, PageParams, page_params
from app.core.security import get_current_user
from app.models.user import OrganizationMembership, User
from app.schemas.projects import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectRead, status_code=201)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # El propietario nunca se toma del cuerpo (un cliente no debe poder crear
    # proyectos a nombre de otro usuario) — se deriva siempre del JWT.
    overrides: dict = {"owner_user_id": current_user.id}
    if payload.organization_id is None and payload.new_organization is None:
        membership = (
            (
                await session.execute(
                    select(OrganizationMembership).where(
                        OrganizationMembership.user_id == current_user.id
                    )
                )
            )
            .scalars()
            .first()
        )
        if membership is not None:
            overrides["organization_id"] = membership.organization_id

    service = ProjectService(session)
    project = await service.create(payload.model_copy(update=overrides))
    return ProjectRead.model_validate(project)


@router.get("/projects", response_model=Page[ProjectRead])
async def list_projects(
    params: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProjectService(session)
    return await service.list(params, owner_user_id=current_user.id)


@router.get("/projects/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProjectService(session)
    project = await service.get(project_id, current_user)
    return ProjectRead.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProjectService(session)
    existing = await service.get(project_id, current_user)
    await service.ensure_access(existing, current_user, write=True)
    project = await service.update(project_id, payload)
    return ProjectRead.model_validate(project)


class ProjectMemberCreate(BaseModel):
    user_id: int = Field(gt=0)
    role_code: Literal["ADMIN", "EDITOR", "VIEWER"]


class ProjectMemberRead(BaseModel):
    user_id: int
    username: str
    role_code: str


@router.get("/projects/{project_id}/members", response_model=list[ProjectMemberRead])
async def list_project_members(
    project_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProjectService(session)
    project = await service.get(project_id, current_user)
    return [ProjectMemberRead(**item) for item in await service.list_members(project, current_user)]


@router.post("/projects/{project_id}/members", response_model=ProjectMemberRead)
async def add_project_member(
    project_id: int,
    payload: ProjectMemberCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProjectService(session)
    project = await service.get(project_id, current_user)
    result = await service.add_member(project, current_user, payload.user_id, payload.role_code)
    return ProjectMemberRead(**result)


@router.delete("/projects/{project_id}/members/{user_id}", status_code=204)
async def remove_project_member(
    project_id: int,
    user_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProjectService(session)
    project = await service.get(project_id, current_user)
    await service.remove_member(project, current_user, user_id)
