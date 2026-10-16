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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.auth_cookie import SESSION_COOKIE, validate_cookie_csrf
from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.models.user import User
from app.models.revoked_token import RevokedAccessToken

_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "scope": "user:access",
        "iat": now,
        "jti": secrets.token_urlsafe(24),
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Token inválido o expirado.") from exc

    if payload.get("scope") != "user:access":
        raise AuthenticationError("Token no autorizado para acceso a cuentas.")
    try:
        return int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Token inválido.") from exc


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


def get_request_access_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = None,
) -> str | None:
    """Use the same Bearer-over-cookie precedence on auth and logout."""
    if credentials is not None:
        return credentials.credentials
    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return request.cookies.get(SESSION_COOKIE)


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
    token = get_request_access_token(request, credentials)
    if not token:
        return None
    if credentials is None:
        validate_cookie_csrf(request)
    user_id = decode_access_token(token)
    if await session.get(RevokedAccessToken, access_token_fingerprint(token)) is not None:
        raise AuthenticationError("La sesión fue cerrada. Inicia sesión nuevamente.")
    user = await session.get(User, user_id)
    if user is None or user.status != "ACTIVE":
        raise AuthenticationError("La cuenta no existe o no está activa.")
    return user


async def get_current_user(
    user: User | None = Depends(get_optional_current_user),
) -> User:
    if user is None:
        raise AuthenticationError("Se requiere autenticación (header Authorization: Bearer <token>).")
    return user
