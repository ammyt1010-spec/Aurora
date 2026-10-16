"""Hashing de password y sesión (JWT). No forma parte del harness backend
original (que asume auth externa vía SSO) — se añade porque Colmena pasa a
tener login/signup propios en esta iteración.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import secrets

import bcrypt
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.auth_cookie import SESSION_COOKIE, validate_cookie_csrf
from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.models.user import User
from app.models.revoked_token import RevokedAccessToken
from app.models.user_session import UserSession

_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    user_id: int, session_version: int = 0, session_id: str | None = None
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "scope": "user:access",
        "sv": session_version,
        "iat": now,
        "jti": secrets.token_urlsafe(24),
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token_claims(token: str) -> dict:
    """Validate signature, expiry and authorization scope before returning claims."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Token inválido o expirado.") from exc

    if payload.get("scope") != "user:access":
        raise AuthenticationError("Token no autorizado para acceso a cuentas.")
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise AuthenticationError("Token inválido.") from exc
    session_version = payload.get("sv", 0)  # Pre-migration access tokens use version 0.
    if user_id <= 0 or type(session_version) is not int or session_version < 0:
        raise AuthenticationError("Versión de sesión inválida.")
    return payload


def decode_access_token(token: str) -> int:
    return int(decode_access_token_claims(token)["sub"])


def access_token_fingerprint(token: str) -> str:
    """Store only a digest of a signed JWT, never the reusable credential."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def access_token_expires_at(token: str) -> datetime:
    """Validate the signed user token and return its signed expiry."""
    decode_access_token(token)
    settings = get_settings()
    claims = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
        options={"require": ["exp"]},
    )
    return datetime.fromtimestamp(int(claims["exp"]), tz=UTC)


def get_bearer_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = None,
) -> str | None:
    if credentials is not None and credentials.credentials:
        return credentials.credentials.strip()
    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return None


def get_cookie_token(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE)
    return token.strip() if token else None


def get_all_request_access_tokens(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = None,
) -> tuple[str | None, str | None]:
    """Return (bearer_token, cookie_token)."""
    return get_bearer_token(request, credentials), get_cookie_token(request)


def get_request_access_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = None,
) -> str | None:
    """Use Bearer-over-cookie precedence when resolving a single token."""
    bearer, cookie = get_all_request_access_tokens(request, credentials)
    return bearer or cookie


async def get_optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User | None:
    """Accept explicit Bearer (API) or HttpOnly session cookie (browser).

    Respondents with X-Response-Token always use their anonymous capability,
    even when an unrelated admin is logged in on the same browser.
    """
    if request.headers.get("X-Response-Token"):
        return None

    bearer_token, cookie_token = get_all_request_access_tokens(request, credentials)
    if not bearer_token and not cookie_token:
        return None

    # CSRF validation is MANDATORY whenever browser session cookies are present on unsafe methods,
    # regardless of whether an Authorization header was also provided.
    if cookie_token is not None:
        validate_cookie_csrf(request)

    # Decode and validate claims for presented credentials
    claims_bearer = decode_access_token_claims(bearer_token) if bearer_token else None
    claims_cookie = decode_access_token_claims(cookie_token) if cookie_token else None

    # Detect credential confusion: if both are sent, they must belong to the exact same account
    if claims_bearer and claims_cookie and claims_bearer["sub"] != claims_cookie["sub"]:
        raise AuthenticationError(
            "Conflicto de credenciales: el token Bearer y la cookie de sesión pertenecen a cuentas distintas."
        )

    # Check revocation for every presented credential
    if bearer_token and await session.get(RevokedAccessToken, access_token_fingerprint(bearer_token)) is not None:
        raise AuthenticationError("La sesión fue cerrada. Inicia sesión nuevamente.")
    if cookie_token and await session.get(RevokedAccessToken, access_token_fingerprint(cookie_token)) is not None:
        raise AuthenticationError("La sesión fue cerrada. Inicia sesión nuevamente.")

    primary_claims = claims_bearer or claims_cookie
    user_id = int(primary_claims["sub"])
    user = await session.get(User, user_id)
    if user is None or user.status != "ACTIVE":
        raise AuthenticationError("La cuenta no existe o no está activa.")

    # Validate session version individually on EVERY presented credential
    if claims_bearer and claims_bearer.get("sv", 0) != user.session_version:
        raise AuthenticationError("La sesión del token Bearer fue invalidada. Inicia sesión nuevamente.")
    if claims_cookie and claims_cookie.get("sv", 0) != user.session_version:
        raise AuthenticationError("La sesión de la cookie fue invalidada. Inicia sesión nuevamente.")

    # Validate individual device session if sid is tracked in claims
    sid_bearer = claims_bearer.get("sid") if claims_bearer else None
    sid_cookie = claims_cookie.get("sid") if claims_cookie else None

    for credential_name, sid in [("Bearer", sid_bearer), ("Cookie", sid_cookie)]:
        if sid:
            result = await session.execute(
                select(UserSession).where(UserSession.session_id == sid)
            )
            db_session = result.scalars().first()
            if db_session is not None:
                if db_session.revoked_at is not None:
                    raise AuthenticationError(f"La sesión {credential_name} fue cerrada o revocada.")
                exp = db_session.expires_at if db_session.expires_at.tzinfo is not None else db_session.expires_at.replace(tzinfo=UTC)
                if exp <= datetime.now(UTC):
                    raise AuthenticationError(f"La sesión {credential_name} ha expirado.")
                now = datetime.now(UTC)
                last_act = db_session.last_activity_at if db_session.last_activity_at.tzinfo is not None else db_session.last_activity_at.replace(tzinfo=UTC)
                if (now - last_act).total_seconds() > 60:
                    db_session.last_activity_at = now
                    await session.flush()

    return user


async def get_current_user(
    user: User | None = Depends(get_optional_current_user),
) -> User:
    if user is None:
        raise AuthenticationError("Se requiere autenticación (header Authorization: Bearer <token>).")
    return user
