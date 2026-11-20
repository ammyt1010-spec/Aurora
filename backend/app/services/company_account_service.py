"""Enterprise account lifecycle, shared by public signup and the platform operator."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.evaluation_entitlement import EvaluationEntitlement
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.auth import CompanyAccountList, CompanyAccountRead, CompanyAccountSummary
from app.services.audit_service import AuditService
from app.services.session_service import SessionService
from app.services.company_email_service import send_confirmation


class CompanyAccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, email: str, username: str, password: str,
        company_name: str, company_ruc: str, company_workers: int | None,
        operator_id: int | None = None,
        verify_email: bool = False,
    ) -> CompanyAccountRead:
        email = email.strip().lower()
        username = username.strip()
        company_name = company_name.strip()
        ruc = company_ruc.strip()
        existing_user = await self.session.scalar(
            select(User.id).where(or_(func.lower(User.email) == email, func.lower(User.username) == username.lower()))
        )
        if existing_user is not None:
            raise ConflictError("Ya existe una cuenta con ese correo o usuario.")
        existing_company = await self.session.scalar(
            select(Organization.id).where(Organization.tax_id == ruc)
        )
        if existing_company is not None:
            raise ConflictError("El RUC ya está registrado. Contacta al administrador de AURORA.")

        user = User(
            email=email, username=username, password_hash=hash_password(password),
            status="PENDING_EMAIL" if verify_email else "ACTIVE",
        )
        self.session.add(user)
        try:
            await self.session.flush()
            organization = Organization(
                name=company_name, legal_name=company_name, tax_id=ruc, status="ACTIVE",
                metadata_={"headcount": company_workers} if company_workers else {},
            )
            self.session.add(organization)
            await self.session.flush()
            user.managed_company_id = organization.id
            # Retain the metadata key until all older deployments have migrated.
            user.metadata_ = {**(user.metadata_ or {}), "managed_company_id": organization.id}
            self.session.add(OrganizationMembership(
                organization_id=organization.id, user_id=user.id, role_code="OWNER", permissions={},
            ))
            await AuditService(self.session).log(
                action="COMPANY_ACCOUNT_ISSUED" if operator_id is not None else "COMPANY_ACCOUNT_SELF_REGISTERED",
                entity_type="user", entity_id=user.id, user_id=operator_id or user.id,
                organization_id=organization.id,
                after_data={"email": email, "company_ruc": ruc, "free_evaluations": 4,
                            "verification_required": verify_email},
            )
            if verify_email:
                await send_confirmation(user, company_name)
                user.metadata_ = {
                    **(user.metadata_ or {}),
                    "email_verification_sent_at": [datetime.now(UTC).isoformat()],
                }
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("El correo, usuario o RUC ya está registrado.") from exc
        except Exception:
            await self.session.rollback()
            raise
        return CompanyAccountRead(
            user_id=user.id, organization_id=organization.id, email=email,
            verification_required=verify_email,
        )

    async def list_accounts(self, *, q: str = "", limit: int = 50, offset: int = 0) -> CompanyAccountList:
        conditions = [User.managed_company_id == Organization.id]
        if q.strip():
            term = f"%{q.strip()}%"
            conditions.append(or_(
                User.email.ilike(term), Organization.name.ilike(term), Organization.tax_id.ilike(term),
            ))
        base = select(User, Organization).where(*conditions)
        total = await self.session.scalar(select(func.count()).select_from(User, Organization).where(*conditions))
        rows = (await self.session.execute(
            base.order_by(User.created_at.desc(), User.id.desc()).limit(limit).offset(offset)
        )).all()
        ids = [user.id for user, _ in rows]
        used = {}
        if ids:
            used = dict((await self.session.execute(
                select(EvaluationEntitlement.user_id, func.count(EvaluationEntitlement.id))
                .where(EvaluationEntitlement.user_id.in_(ids), EvaluationEntitlement.access_kind == "FREE")
                .group_by(EvaluationEntitlement.user_id)
            )).all())
        return CompanyAccountList(
            items=[self._summary(user, org, int(used.get(user.id, 0))) for user, org in rows],
            total=int(total or 0),
        )

    async def set_status(self, user_id: int, status: str, *, operator_id: int) -> CompanyAccountSummary:
        user, org = await self._get_managed(user_id)
        before = user.status
        if before != status:
            user.status = status
            user.session_version += 1
            await SessionService(self.session).revoke_all_sessions(user.id, reason="OPERATOR_ACCOUNT_STATUS")
            await AuditService(self.session).log(
                action="COMPANY_ACCOUNT_STATUS_CHANGED", entity_type="user", entity_id=user.id,
                user_id=operator_id, organization_id=org.id,
                before_data={"status": before}, after_data={"status": status},
            )
            await self.session.commit()
        return self._summary(user, org, await self._free_used(user.id))

    async def reset_password(self, user_id: int, password: str, *, operator_id: int) -> None:
        user, org = await self._get_managed(user_id)
        user.password_hash = hash_password(password)
        user.session_version += 1
        await SessionService(self.session).revoke_all_sessions(user.id, reason="OPERATOR_PASSWORD_RESET")
        await AuditService(self.session).log(
            action="COMPANY_ACCOUNT_PASSWORD_RESET", entity_type="user", entity_id=user.id,
            user_id=operator_id, organization_id=org.id,
        )
        await self.session.commit()

    async def _get_managed(self, user_id: int) -> tuple[User, Organization]:
        user = await self.session.get(User, user_id)
        org = await self.session.get(Organization, user.managed_company_id) if user and user.managed_company_id else None
        if user is None or org is None:
            raise NotFoundError("Cuenta empresarial no encontrada.")
        return user, org

    async def _free_used(self, user_id: int) -> int:
        return int(await self.session.scalar(
            select(func.count(EvaluationEntitlement.id)).where(
                EvaluationEntitlement.user_id == user_id, EvaluationEntitlement.access_kind == "FREE",
            )
        ) or 0)

    @staticmethod
    def _summary(user: User, org: Organization, used: int) -> CompanyAccountSummary:
        return CompanyAccountSummary(
            user_id=user.id, organization_id=org.id, email=user.email or "",
            username=user.username or "", company_name=org.legal_name or org.name,
            company_ruc=org.tax_id or "", company_workers=(org.metadata_ or {}).get("headcount"),
            status=user.status, created_at=user.created_at,
            free_used=used, free_remaining=max(0, 4 - used),
        )
