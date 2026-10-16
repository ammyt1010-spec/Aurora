from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.rate_limit import enforce_login_rate_limit, enforce_registration_rate_limit
from app.core.auth_cookie import add_session_cookies, clear_session_cookies
from app.core.exceptions import AuthenticationError
from app.core.database import get_db
from app.core.network_security import is_direct_local_request
from app.core.security import (
    access_token_expires_at,
    access_token_fingerprint,
    decode_access_token_claims,
    get_all_request_access_tokens,
    get_current_user,
    get_request_access_token,
)
from app.models.audit import AuditLog
from app.models.user import User
from app.models.revoked_token import RevokedAccessToken
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.services.auth_service import AuthService
from app.services.session_service import SessionService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201,
    dependencies=[Depends(enforce_registration_rate_limit)])
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_db)):
    service = AuthService(session)
    user = await service.register(payload)
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse,
    dependencies=[Depends(enforce_login_rate_limit)])
async def login(payload: LoginRequest, request: Request, response: Response, session: AsyncSession = Depends(get_db)):
    service = AuthService(session)
    token = await service.login(payload, request=request)
    add_session_cookies(response, token, request)
    return TokenResponse(access_token=token)


@router.post("/demo-login", response_model=TokenResponse)
async def demo_login(request: Request, response: Response, session: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if settings.environment.lower() not in {"development", "test", "local"} or not settings.demo_access_enabled:
        raise AuthenticationError("El acceso demo no está disponible en este entorno o instancia.")
    if not is_direct_local_request(request):
        raise AuthenticationError(
            "El acceso demo solo está disponible en conexiones directas de loopback local, "
            "no a través de túneles o proxies públicos."
        )
    service = AuthService(session)
    token = await service.demo_login(settings.demo_user_email, request=request)
    add_session_cookies(response, token, request)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)):
    return UserRead.model_validate(current_user)

@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Revoke ALL credentials presented in this request (Bearer and/or Cookie) then clear cookies."""
    bearer_token, cookie_token = get_all_request_access_tokens(request)
    tokens_to_revoke = {t for t in (bearer_token, cookie_token) if t}
    if not tokens_to_revoke:
        raise AuthenticationError("No hay una sesión activa para cerrar.")

    # Revoke individual device session if sid is present in presented claims
    session_service = SessionService(session)
    for token in tokens_to_revoke:
        claims = decode_access_token_claims(token)
        sid = claims.get("sid")
        if sid:
            await session_service.revoke_user_session(current_user.id, sid, reason="USER_LOGOUT")

    # Record auditable logout event
    audit = AuditLog(
        user_id=current_user.id,
        action="USER_LOGOUT",
        entity_type="user",
        entity_id=current_user.id,
    )
    session.add(audit)

    # Clear expired records opportunistically; do not retain them indefinitely.
    await session.execute(
        delete(RevokedAccessToken).where(RevokedAccessToken.expires_at < datetime.now(UTC))
    )

    dialect = session.get_bind().dialect.name
    for token in tokens_to_revoke:
        token_hash = access_token_fingerprint(token)
        values = {
            "token_hash": token_hash,
            "user_id": current_user.id,
            "expires_at": access_token_expires_at(token),
        }
        if dialect == "postgresql":
            statement = postgres_insert(RevokedAccessToken).values(**values)
        elif dialect == "sqlite":
            statement = sqlite_insert(RevokedAccessToken).values(**values)
        else:
            raise RuntimeError("La revocación de sesiones requiere PostgreSQL o SQLite.")
        await session.execute(statement.on_conflict_do_nothing(index_elements=["token_hash"]))

    await session.commit()
    clear_session_cookies(response, request)
    return None


@router.post("/logout-all", status_code=204)
async def logout_all(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Invalidate every existing access token for the requesting account across all devices."""
    await session.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(session_version=User.session_version + 1)
    )

    # Invalidate all active sessions in UserSession and record audit log
    await SessionService(session).revoke_all_sessions(current_user.id, reason="GLOBAL_LOGOUT")

    # Also opportunistically record presented tokens in RevokedAccessToken
    bearer_token, cookie_token = get_all_request_access_tokens(request)
    tokens_to_revoke = {t for t in (bearer_token, cookie_token) if t}
    if tokens_to_revoke:
        dialect = session.get_bind().dialect.name
        for token in tokens_to_revoke:
            values = {
                "token_hash": access_token_fingerprint(token),
                "user_id": current_user.id,
                "expires_at": access_token_expires_at(token),
            }
            if dialect == "postgresql":
                statement = postgres_insert(RevokedAccessToken).values(**values)
            elif dialect == "sqlite":
                statement = sqlite_insert(RevokedAccessToken).values(**values)
            else:
                statement = None
            if statement is not None:
                await session.execute(statement.on_conflict_do_nothing(index_elements=["token_hash"]))

    await session.commit()
    clear_session_cookies(response, request)
    return None
