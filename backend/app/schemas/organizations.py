from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str = Field(min_length=3, max_length=80)
    organization_type: str | None = Field(default=None, max_length=80)


class OrganizationRead(BaseModel):
    id: int
    public_id: uuid.UUID
    name: str
    legal_name: str | None
    tax_id: str | None
    organization_type: str | None
    status: str

    model_config = ConfigDict(from_attributes=True)


class OrganizationMembershipRead(BaseModel):
    organization: OrganizationRead
    role_code: str
    permissions: dict
    declared_workers: int | None = None


class CollaboratorCodeCreate(BaseModel):
    label: str = Field(default="Colaboradores", min_length=1, max_length=120)


class CollaboratorCodeRead(BaseModel):
    id: int
    organization_id: int
    label: str
    code_prefix: str
    code: str | None = None
    status: str
    created_by_user_id: int
    created_at: datetime
    revoked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class JoinOrganizationRequest(BaseModel):
    code: str = Field(min_length=8, max_length=120)


class JoinOrganizationResponse(BaseModel):
    organization: OrganizationRead
    role_code: str
