from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cookie import clear_session_cookies
from app.core.config import get_settings
from app.core.exceptions import AuthorizationError, AuthenticationError
from app.core.database import get_db
from app.core.security import (
    decode_access_token_claims,
    get_all_request_access_tokens,
    get_current_user,
)
from app.models.user import User
from app.schemas.session import (
    SessionCleanupResponse,
    SessionRevokeResponse,
    UserSessionRead,
)
from app.services.session_service import SessionService

router = APIRouter(prefix="/auth/sessions", tags=["sessions"])


def get_current_session_id(request: Request) -> str | None:
    bearer, cookie = get_all_request_access_tokens(request)
    for token in (bearer, cookie):
        if token:
            try:
                claims = decode_access_token_claims(token)
                sid = claims.get("sid")
                if sid:
                    return str(sid)
            except Exception:
                pass
    return None


@router.get("", response_model=list[UserSessionRead])
async def list_my_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all active device sessions for the authenticated user."""
    current_sid = get_current_session_id(request)
    service = SessionService(session)
    return await service.list_user_sessions(current_user.id, current_sid=current_sid)


@router.delete("/{session_id}", status_code=204)
async def revoke_my_session(
    session_id: str,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Revoke a specific device session. If it's the current session, also clear cookies."""
    service = SessionService(session)
    await service.revoke_user_session(current_user.id, session_id, reason="USER_REVOKED")
    current_sid = get_current_session_id(request)
    if current_sid == session_id:
        clear_session_cookies(response, request)
    await session.commit()
    return None


@router.delete("", response_model=SessionRevokeResponse)
async def revoke_other_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Revoke all active device sessions except the one currently in use."""
    current_sid = get_current_session_id(request)
    if not current_sid:
        raise AuthenticationError("Para cerrar otras sesiones, inicia sesión nuevamente desde este dispositivo.")
    bearer, cookie = get_all_request_access_tokens(request)
    if bearer and cookie:
        bearer_sid = decode_access_token_claims(bearer).get("sid")
        cookie_sid = decode_access_token_claims(cookie).get("sid")
        if bearer_sid != cookie_sid:
            raise AuthenticationError("Sesión ambigua: renueva las credenciales antes de cerrar otros dispositivos.")
    service = SessionService(session)
    count = await service.revoke_other_sessions(current_user.id, current_sid=current_sid)
    await session.commit()
    return SessionRevokeResponse(
        revoked_count=count,
        message=f"Se cerraron {count} sesiones en otros dispositivos.",
    )


@router.post("/cleanup", response_model=SessionCleanupResponse)
async def cleanup_sessions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Privileged maintenance only: never expose a global purge to all accounts."""
    operator_id = get_settings().session_maintenance_operator_user_id
    if operator_id is None or current_user.id != operator_id:
        raise AuthorizationError("Mantenimiento reservado al operador de seguridad autorizado.")
    service = SessionService(session)
    purged_sessions, purged_tokens = await service.cleanup_expired_sessions()
    await session.commit()
    return SessionCleanupResponse(
        purged_sessions_count=purged_sessions,
        purged_revoked_tokens_count=purged_tokens,
    )
