from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationDomainError
from app.models.analytics_plan import OrganizationCollaboratorCode
from app.models.project import Project
from app.models.user import Organization, OrganizationMembership, User
from app.services.audit_service import AuditService
from app.schemas.organizations import (
    CollaboratorCodeCreate,
    OrganizationCreate,
    JoinOrganizationRequest,
)


def _normalize_tax_id(value: str) -> str:
    return "".join(value.split()).upper()


def _hash_code(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class OrganizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: int) -> list[tuple[Organization, str, dict]]:
        stmt = (
            select(Organization, OrganizationMembership.role_code, OrganizationMembership.permissions)
            .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
            .where(OrganizationMembership.user_id == user_id, Organization.status == "ACTIVE")
            .order_by(Organization.name, Organization.id)
        )
        return list((await self.session.execute(stmt)).all())

    async def create(
        self, payload: OrganizationCreate, user: User, *, commit: bool = True
    ) -> Organization:
        tax_id = _normalize_tax_id(payload.tax_id)
        existing = await self._by_tax_id(tax_id)
        if existing is not None:
            raise ConflictError(
                "La empresa ya está registrada. Solicita un código de colaborador al administrador.",
                organization_exists=True,
            )
        organization = Organization(
            name=payload.name.strip(),
            legal_name=payload.legal_name.strip() if payload.legal_name else None,
            tax_id=tax_id,
            organization_type=payload.organization_type,
            status="ACTIVE",
        )
        self.session.add(organization)
        await self.session.flush()
        self.session.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role_code="OWNER",
                permissions={},
            )
        )
        await AuditService(self.session).log(
            action="ORGANIZATION_CREATED", entity_type="organization",
            entity_id=organization.id, organization_id=organization.id,
            user_id=user.id,
        )
        if commit:
            await self.session.commit()
            await self.session.refresh(organization)
        return organization

    async def get_for_member(self, organization_id: int, user: User) -> Organization:
        organization = await self.session.get(Organization, organization_id)
        if organization is None or organization.status != "ACTIVE":
            raise NotFoundError(f"Organización {organization_id} no encontrada")
        member = await self._membership(organization_id, user.id)
        if member is None:
            raise ValidationDomainError("No perteneces a esta organización.")
        return organization

    async def create_code(
        self, organization_id: int, payload: CollaboratorCodeCreate, user: User
    ) -> tuple[OrganizationCollaboratorCode, str]:
        organization = await self.get_for_member(organization_id, user)
        member = await self._membership(organization.id, user.id)
        if member is None or member.role_code not in {"OWNER", "ADMIN"}:
            raise AuthorizationError("Sólo OWNER o ADMIN puede crear códigos.")
        raw_code = f"COL-{secrets.token_urlsafe(18)}"
        code = OrganizationCollaboratorCode(
            organization_id=organization.id,
            label=payload.label,
            code_prefix=raw_code[:12],
            code_hash=_hash_code(raw_code),
            status="ACTIVE",
            created_by_user_id=user.id,
        )
        self.session.add(code)
        await self.session.flush()
        # Audit the identifier only. The raw invitation secret is never persisted in logs.
        await AuditService(self.session).log(
            action="COLLABORATOR_CODE_CREATED", entity_type="collaborator_code",
            entity_id=code.id, organization_id=organization.id,
            user_id=user.id,
        )
        await self.session.commit()
        await self.session.refresh(code)
        return code, raw_code

    async def list_codes(self, organization_id: int, user: User) -> list[OrganizationCollaboratorCode]:
        organization = await self.get_for_member(organization_id, user)
        member = await self._membership(organization.id, user.id)
        if member is None or member.role_code not in {"OWNER", "ADMIN"}:
            raise AuthorizationError("Sólo OWNER o ADMIN puede administrar códigos.")
        stmt = select(OrganizationCollaboratorCode).where(
            OrganizationCollaboratorCode.organization_id == organization.id
        ).order_by(OrganizationCollaboratorCode.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def revoke_code(self, organization_id: int, code_id: int, user: User) -> OrganizationCollaboratorCode:
        await self.get_for_member(organization_id, user)
        member = await self._membership(organization_id, user.id)
        if member is None or member.role_code not in {"OWNER", "ADMIN"}:
            raise AuthorizationError("Sólo OWNER o ADMIN puede revocar códigos.")
        code = await self.session.get(OrganizationCollaboratorCode, code_id)
        if code is None or code.organization_id != organization_id:
            raise NotFoundError(f"Código {code_id} no encontrado")
        code.status = "REVOKED"
        code.revoked_at = datetime.now(UTC)
        await AuditService(self.session).log(
            action="COLLABORATOR_CODE_REVOKED", entity_type="collaborator_code",
            entity_id=code.id, organization_id=organization_id,
            user_id=user.id,
        )
        await self.session.commit()
        await self.session.refresh(code)
        return code

    async def join(self, payload: JoinOrganizationRequest, user: User) -> Organization:
        code = await self.session.execute(
            select(OrganizationCollaboratorCode).where(
                OrganizationCollaboratorCode.code_hash == _hash_code(payload.code.strip()),
                OrganizationCollaboratorCode.status == "ACTIVE",
            )
        )
        invitation = code.scalars().first()
        if invitation is None:
            raise ValidationDomainError("El código no existe o fue revocado.")
        organization = await self.session.get(Organization, invitation.organization_id)
        if organization is None or organization.status != "ACTIVE":
            raise NotFoundError("La organización del código no está disponible")
        membership = await self._membership(organization.id, user.id)
        if membership is None:
            self.session.add(
                OrganizationMembership(
                    organization_id=organization.id,
                    user_id=user.id,
                    role_code="COLLABORATOR",
                    permissions={"read": True},
                )
            )
            await AuditService(self.session).log(
                action="ORGANIZATION_MEMBER_JOINED", entity_type="organization_member",
                entity_id=user.id, organization_id=organization.id, user_id=user.id,
            )
            await self.session.commit()
        return organization

    async def _by_tax_id(self, tax_id: str) -> Organization | None:
        stmt = select(Organization).where(Organization.tax_id == tax_id)
        return (await self.session.execute(stmt)).scalars().first()

    async def _membership(self, organization_id: int, user_id: int) -> OrganizationMembership | None:
        stmt = select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
        return (await self.session.execute(stmt)).scalars().first()
