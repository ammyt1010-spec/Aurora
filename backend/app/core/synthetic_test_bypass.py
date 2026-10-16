"""Fail-closed authorization of synthetic, unlicensed report generation.

Never trust loopback addresses, Host, or proxy headers for commercial access.
Pytest can explicitly enable a short-lived test token; regular app instances
(including development, staging and production) always require a paid order.
"""
from __future__ import annotations

import secrets
from fastapi import Request
from app.core.config import Settings, get_settings


def is_authorized_synthetic_test(request: Request | None, settings: Settings | None = None) -> bool:
    config = settings if settings is not None else get_settings()
    if config.environment.lower() != "test" or not config.allow_synthetic_test_bypass:
        return False
    secret = config.test_bypass_secret
    if request is None or not secret or len(secret) < 43:
        return False
    supplied = request.headers.get("X-Aurora-Test-Token", "")
    if not supplied or len(supplied) > 256:
        return False
    return secrets.compare_digest(supplied, secret)
