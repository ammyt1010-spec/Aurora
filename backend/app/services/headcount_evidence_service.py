"""Operator-approved, revocable headcount evidence with stable audit history.

The digest is provided after a human validates the original document in a
separate secure records system. No automatic documentary authenticity is claimed.
"""
from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationDomainError
from app.models.headcount_evidence import HeadcountEvidence
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.headcount_evidence import HeadcountEvidenceApprove
from app.services.audit_service import AuditService
from app.services.billing_service import is_platform_operator, require_operator


class HeadcountEvidenceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_history(self, organization_id: int, user: User) -> list[HeadcountEvidence]:
        if not is_platform_operator(user):
            membership = await self.db.get(OrganizationMembership, (organization_id, user.id))
            if membership is None or membership.role_code not in {"OWNER", "ADMIN"}:
                raise AuthorizationError("Solo el operador o un administrador de la empresa puede consultar evidencias.")
        org = await self.db.get(Organization, organization_id)
        if org is None:
            raise NotFoundError("Empresa no encontrada.")
        return list((await self.db.execute(
            select(HeadcountEvidence)
            .where(HeadcountEvidence.organization_id == organization_id)
            .order_by(HeadcountEvidence.id.desc())
        )).scalars().all())

    async def approve(self, organization_id: int, payload: HeadcountEvidenceApprove, user: User) -> HeadcountEvidence:
        require_operator(user)
        now = datetime.now(UTC)
        if payload.valid_until <= now:
            raise ValidationDomainError("La vigencia documental debe ser futura.")
        org = (await self.db.execute(
            select(Organization).where(Organization.id == organization_id).with_for_update()
        )).scalar_one_or_none()
        if org is None or org.status != "ACTIVE":
            raise NotFoundError("Empresa activa no encontrada.")
        duplicate = (await self.db.execute(select(HeadcountEvidence.id).where(
            HeadcountEvidence.organization_id == organization_id,
            HeadcountEvidence.source_type == payload.source_type,
            HeadcountEvidence.document_sha256 == payload.document_sha256,
        ))).scalar_one_or_none()
        if duplicate is not None:
            raise ConflictError("El mismo documento ya tiene una revisión registrada. Utiliza una nueva evidencia.")
        # Row-level serialization on organization prevents two active revisions of the same source.
        old_records = (await self.db.execute(select(HeadcountEvidence).where(
            HeadcountEvidence.organization_id == organization_id,
            HeadcountEvidence.source_type == payload.source_type,
            HeadcountEvidence.revoked_at.is_(None),
        ).with_for_update())).scalars().all()
        for previous in old_records:
            previous.revoked_at = now
            previous.revoked_by_user_id = user.id
            await AuditService(self.db).log(
                action="HEADCOUNT_EVIDENCE_SUPERSEDED", entity_type="headcount_evidence",
                entity_id=previous.id, organization_id=organization_id, user_id=user.id,
                after_data={"source_type": previous.source_type},
            )
        record = HeadcountEvidence(
            organization_id=organization_id, source_type=payload.source_type,
            workers=payload.workers, document_sha256=payload.document_sha256,
            evidence_reference=payload.evidence_reference,
            verified_by_user_id=user.id, verified_at=now, valid_until=payload.valid_until,
        )
        self.db.add(record)
        await self.db.flush()
        await AuditService(self.db).log(
            action="HEADCOUNT_EVIDENCE_APPROVED", entity_type="headcount_evidence",
            entity_id=record.id, organization_id=organization_id, user_id=user.id,
            after_data={"source_type": payload.source_type, "workers": payload.workers, "valid_until": payload.valid_until.isoformat()},
        )
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def revoke(self, organization_id: int, evidence_id: int, user: User) -> HeadcountEvidence:
        require_operator(user)
        record = (await self.db.execute(
            select(HeadcountEvidence).where(
                HeadcountEvidence.id == evidence_id, HeadcountEvidence.organization_id == organization_id
            ).with_for_update()
        )).scalar_one_or_none()
        if record is None:
            raise NotFoundError("Evidencia no encontrada.")
        if record.revoked_at is not None:
            raise ConflictError("Esta revisión documental ya está revocada.")
        record.revoked_at = datetime.now(UTC)
        record.revoked_by_user_id = user.id
        await AuditService(self.db).log(
            action="HEADCOUNT_EVIDENCE_REVOKED", entity_type="headcount_evidence",
            entity_id=record.id, organization_id=organization_id, user_id=user.id,
            after_data={"source_type": record.source_type},
        )
        await self.db.commit()
        await self.db.refresh(record)
        return record
