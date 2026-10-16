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


def is_request_secure(request: Request | None = None) -> bool:
    """Detect if the connection is HTTPS directly or terminated by a TLS reverse proxy."""
    settings = get_settings()
    if settings.environment.lower() == "production":
        return True
    if request is None:
        return False

    # Direct HTTPS scheme
    if getattr(request, "url", None) and request.url.scheme == "https":
        return True

    # Standard proxy TLS termination headers
    headers = request.headers
    if headers.get("x-forwarded-proto", "").lower() == "https":
        return True
    if headers.get("x-forwarded-ssl", "").lower() == "on":
        return True
    if '"scheme":"https"' in headers.get("cf-visitor", ""):
        return True
    if headers.get("front-end-https", "").lower() == "on":
        return True

    return False


def add_session_cookies(response: Response, token: str, request: Request | None = None) -> None:
    settings = get_settings()
    secure = is_request_secure(request)
    samesite = "strict" if secure else "lax"
    ttl = settings.jwt_expire_minutes * 60
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, secure=secure,
        samesite=samesite, max_age=ttl, path="/api/v1",
    )
    response.set_cookie(
        CSRF_COOKIE, secrets.token_urlsafe(32), httponly=False,
        secure=secure, samesite=samesite, max_age=ttl, path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def clear_session_cookies(response: Response, request: Request | None = None) -> None:
    secure = is_request_secure(request)
    samesite = "strict" if secure else "lax"
    response.delete_cookie(SESSION_COOKIE, path="/api/v1", secure=secure, samesite=samesite)
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure, samesite=samesite)
    response.headers["Cache-Control"] = "no-store"


def validate_cookie_csrf(request: Request) -> None:
    if request.method.upper() not in UNSAFE_METHODS:
        return
    expected = request.cookies.get(CSRF_COOKIE, "")
    provided = request.headers.get(CSRF_HEADER, "")
    if not expected or not provided or not secrets.compare_digest(expected, provided):
        raise AuthorizationError("Sesión de navegador: protección CSRF inválida.")
