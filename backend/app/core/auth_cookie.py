"""Browser-session cookie and CSRF policy, isolated from JWT decoding.

Bearer authentication is retained for CLI/API clients. The browser never
needs to persist bearer tokens in JavaScript storage.
"""
from __future__ import annotations

import secrets

from fastapi import Request, Response

from app.core.config import get_settings
from app.core.exceptions import AuthorizationError

SESSION_COOKIE = "aurora_session"
CSRF_COOKIE = "aurora_csrf"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def add_session_cookies(response: Response, token: str) -> None:
    settings = get_settings()
    secure = settings.environment.lower() == "production"
    ttl = settings.jwt_expire_minutes * 60
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, secure=secure,
        samesite="strict", max_age=ttl, path="/api/v1",
    )
    response.set_cookie(
        CSRF_COOKIE, secrets.token_urlsafe(32), httponly=False,
        secure=secure, samesite="strict", max_age=ttl, path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/api/v1")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"


def validate_cookie_csrf(request: Request) -> None:
    if request.method.upper() not in UNSAFE_METHODS:
        return
    expected = request.cookies.get(CSRF_COOKIE, "")
    provided = request.headers.get(CSRF_HEADER, "")
    if not expected or not provided or not secrets.compare_digest(expected, provided):
        raise AuthorizationError("Sesión de navegador: protección CSRF inválida.")
