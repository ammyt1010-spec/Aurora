from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    first_name: str | None = None
    last_name: str | None = None


class CompanyAccountCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=120)
    initial_password: str = Field(min_length=12, max_length=128)
    company_name: str = Field(min_length=2, max_length=255)
    company_ruc: str = Field(pattern=r"^\d{11}$")
    company_workers: int | None = Field(default=None, ge=1, le=10_000_000)


class CompanySignupRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    company_name: str = Field(min_length=2, max_length=255)
    company_ruc: str = Field(pattern=r"^\d{11}$")
    company_workers: int = Field(ge=1, le=10_000_000)


class CompanyAccountRead(BaseModel):
    user_id: int
    organization_id: int
    email: EmailStr
    free_evaluations: int = 4
    verification_required: bool = False


class VerifyCompanyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=2048)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class CompanyAccountSummary(BaseModel):
    user_id: int
    organization_id: int
    email: str
    username: str
    company_name: str
    company_ruc: str
    company_workers: int | None
    status: str
    created_at: datetime
    free_used: int
    free_remaining: int


class CompanyAccountList(BaseModel):
    items: list[CompanyAccountSummary]
    total: int


class CompanyAccountStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(ACTIVE|SUSPENDED)$")


class CompanyAccountPasswordReset(BaseModel):
    new_password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    id: int
    public_id: uuid.UUID
    email: str | None
    username: str | None
    first_name: str | None
    last_name: str | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
