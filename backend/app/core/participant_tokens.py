"""Short-lived, session-bound JWT capability for anonymous survey respondents."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError


def create_participant_token(session_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(session_id), "scope": "survey:answer", "iat": now, "exp": now + timedelta(hours=48)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_participant_token(token: str, session_id: int) -> None:
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if claims.get("scope") != "survey:answer" or claims.get("sub") != str(session_id):
            raise AuthenticationError("El token no corresponde a esta sesión.")
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Token de encuesta inválido o vencido.") from exc
