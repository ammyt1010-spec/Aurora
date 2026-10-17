"""Emisión y consumo de tokens de invitación de un solo uso (E-17).

El token en texto plano sólo existe en el momento de `issue`: se retorna al
llamador (para distribuirlo por el canal que corresponda) y nunca se
persiste — sólo su hash SHA-256. SHA-256 y no bcrypt: el token ya es de alta
entropía (`secrets.token_urlsafe`), y hace falta poder buscarlo por
igualdad exacta de hash (`WHERE access_token_hash = ...`); bcrypt no lo
permite porque cada hash incluye una sal distinta por diseño.
"""

from __future__ import annotations

import hashlib
import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import UTC, datetime
from app.core.exceptions import ConflictError, NotFoundError, ValidationDomainError
from app.services.audit_service import AuditService
from app.models.participant import StudyInvitation
from app.repositories.studies import StudyRepository


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(32)


def hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class InvitationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.study_repo = StudyRepository(session)

    async def issue(self, study_id: int, count: int) -> list[str]:
        study = await self.study_repo.get(study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")
        if not 1 <= count <= 1000:
            raise ValidationDomainError("La cantidad de invitaciones debe estar entre 1 y 1000.")
        if not study.requires_invitation:
            raise ConflictError("Este estudio no tiene activado el acceso por invitaciones.")
        if study.status != "OPEN":
            raise ConflictError("Sólo se pueden emitir invitaciones para estudios abiertos.")
        if study.end_at is not None:
            end_at = study.end_at if study.end_at.tzinfo else study.end_at.replace(tzinfo=UTC)
            if datetime.now(UTC) >= end_at:
                raise ConflictError("La campaña terminó; no se pueden emitir invitaciones.")

        tokens: list[str] = []
        for _ in range(count):
            token = generate_invitation_token()
            tokens.append(token)
            self.session.add(
                StudyInvitation(
                    study_id=study_id,
                    access_token_hash=hash_invitation_token(token),
                    status="PENDING",
                )
            )
        await self.session.commit()
        return tokens

    async def summary(self, study_id: int, include_revoked: bool = False) -> dict:
        study = await self.study_repo.get(study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")

        stmt = (
            select(StudyInvitation.status, func.count())
            .where(StudyInvitation.study_id == study_id)
            .group_by(StudyInvitation.status)
        )
        counts = dict((await self.session.execute(stmt)).all())
        res = {
            "total": sum(counts.values()),
            "pending": counts.get("PENDING", 0) + counts.get("SENT", 0),
            "consumed": counts.get("CONSUMED", 0),
            "expired": counts.get("EXPIRED", 0),
        }
        if include_revoked:
            res["revoked"] = counts.get("REVOKED", 0)
        return res

    async def list_invitations(
        self, study_id: int, status: str | None = None
    ) -> list[StudyInvitation]:
        study = await self.study_repo.get(study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")

        stmt = select(StudyInvitation).where(StudyInvitation.study_id == study_id)
        if status:
            stmt = stmt.where(StudyInvitation.status == status)
        stmt = stmt.order_by(StudyInvitation.id.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def revoke(
        self, study_id: int, invitation_id: int, reason: str | None = None,
        *, user_id: int | None = None,
    ) -> StudyInvitation:
        study = await self.study_repo.get(study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")
        stmt = select(StudyInvitation).where(
            StudyInvitation.id == invitation_id, StudyInvitation.study_id == study_id
        )
        invitation = (await self.session.execute(stmt)).scalar_one_or_none()
        if invitation is None:
            raise NotFoundError(f"Invitación {invitation_id} no encontrada en este estudio")
        if invitation.status == "CONSUMED":
            raise ConflictError("No se puede revocar una invitación que ya ha sido consumida.")
        if invitation.status == "REVOKED":
            return invitation

        invitation.status = "REVOKED"
        meta = dict(invitation.metadata_ or {})
        meta["revoked_at"] = datetime.now(UTC).isoformat()
        if reason:
            meta["revocation_reason"] = reason
        invitation.metadata_ = meta
        await AuditService(self.session).log(
            action="STUDY_INVITATION_REVOKED",
            entity_type="study_invitation",
            entity_id=invitation.id,
            user_id=user_id,
            project_id=study.project_id,
            after_data={"status": "REVOKED", "reason": reason},
        )
        await self.session.commit()
        await self.session.refresh(invitation)
        return invitation
