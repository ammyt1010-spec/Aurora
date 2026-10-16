from __future__ import annotations

from datetime import UTC, datetime, timedelta
import secrets

from fastapi import Request
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.device_parser import anonymize_ip, parse_device_info
from app.core.exceptions import NotFoundError
from app.core.security import create_access_token
from app.models.audit import AuditLog
from app.models.revoked_token import RevokedAccessToken
from app.models.user import User
from app.models.user_session import UserSession
from app.schemas.session import UserSessionRead


class SessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_user_session(
        self, user: User, request: Request | None = None
    ) -> tuple[str, str]:
        session_id = secrets.token_urlsafe(32)
        settings = get_settings()
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=settings.jwt_expire_minutes)

        ua = request.headers.get("user-agent") if request else None
        dev_info = parse_device_info(ua)
        raw_ip = request.client.host if request and request.client else None
        ip_addr = anonymize_ip(raw_ip)

        user_session = UserSession(
            user_id=user.id,
            session_id=session_id,
            session_version=user.session_version,
            ip_address=ip_addr,
            user_agent=None,  # UA is parsed transiently; do not retain raw tracking data.
            device_family=dev_info["device_family"],
            os_family=dev_info["os_family"],
            browser_family=dev_info["browser_family"],
            created_at=now,
            last_activity_at=now,
            expires_at=expires_at,
        )
        self.session.add(user_session)
        await self.session.flush()

        audit = AuditLog(
            user_id=user.id,
            action="USER_LOGIN",
            entity_type="user_session",
            entity_id=user_session.id,
            after_data={
                "device_family": dev_info["device_family"],
                "os_family": dev_info["os_family"],
                "browser_family": dev_info["browser_family"],
            },
        )
        self.session.add(audit)
        await self.session.flush()

        token = create_access_token(
            user.id, user.session_version, session_id=session_id
        )
        return token, session_id

    async def list_user_sessions(
        self, user_id: int, current_sid: str | None = None
    ) -> list[UserSessionRead]:
        now = datetime.now(UTC)
        stmt = (
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
            .order_by(UserSession.last_activity_at.desc())
        )
        result = await self.session.execute(stmt)
        sessions = result.scalars().all()
        return [
            UserSessionRead(
                session_id=s.session_id,
                device_family=s.device_family,
                os_family=s.os_family,
                browser_family=s.browser_family,
                ip_address=s.ip_address,
                created_at=s.created_at,
                last_activity_at=s.last_activity_at,
                expires_at=s.expires_at,
                is_current=(s.session_id == current_sid),
            )
            for s in sessions
        ]

    async def revoke_user_session(
        self, user_id: int, session_id: str, reason: str = "USER_REVOKED"
    ) -> bool:
        stmt = select(UserSession).where(
            UserSession.session_id == session_id, UserSession.user_id == user_id
        )
        s = (await self.session.execute(stmt)).scalars().first()
        if s is None:
            raise NotFoundError("Sesión no encontrada.")

        if s.revoked_at is None:
            now = datetime.now(UTC)
            s.revoked_at = now
            s.revoked_reason = reason
            audit = AuditLog(
                user_id=user_id,
                action="USER_SESSION_REVOKED",
                entity_type="user_session",
                entity_id=s.id,
                after_data={"reason": reason},
            )
            self.session.add(audit)
            await self.session.flush()
        return True

    async def revoke_other_sessions(
        self, user_id: int, current_sid: str | None
    ) -> int:
        now = datetime.now(UTC)
        stmt = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        if current_sid:
            stmt = stmt.where(UserSession.session_id != current_sid)

        sessions = (await self.session.execute(stmt)).scalars().all()
        for s in sessions:
            s.revoked_at = now
            s.revoked_reason = "USER_REVOKED_OTHERS"

        if sessions:
            audit = AuditLog(
                user_id=user_id,
                action="USER_SESSIONS_REVOKED_OTHERS",
                entity_type="user_session",
                after_data={"revoked_count": len(sessions)},
            )
            self.session.add(audit)
            await self.session.flush()
        return len(sessions)

    async def revoke_all_sessions(
        self, user_id: int, reason: str = "GLOBAL_LOGOUT"
    ) -> int:
        now = datetime.now(UTC)
        stmt = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        sessions = (await self.session.execute(stmt)).scalars().all()
        for s in sessions:
            s.revoked_at = now
            s.revoked_reason = reason

        if sessions:
            audit = AuditLog(
                user_id=user_id,
                action="USER_LOGOUT_ALL",
                entity_type="user",
                entity_id=user_id,
                after_data={"revoked_count": len(sessions), "reason": reason},
            )
            self.session.add(audit)
            await self.session.flush()
        return len(sessions)

    async def cleanup_expired_sessions(self) -> tuple[int, int]:
        now = datetime.now(UTC)
        threshold = now - timedelta(days=30)
        del_sessions = await self.session.execute(
            delete(UserSession).where(
                or_(
                    UserSession.expires_at < threshold,
                    and_(
                        UserSession.revoked_at.is_not(None),
                        UserSession.expires_at < now,
                    ),
                )
            )
        )
        del_revoked = await self.session.execute(
            delete(RevokedAccessToken).where(RevokedAccessToken.expires_at < now)
        )
        await self.session.flush()
        return del_sessions.rowcount, del_revoked.rowcount
