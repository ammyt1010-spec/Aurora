import pytest
from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import RateLimitExceededError
from app.core.rate_limit import enforce_login_rate_limit


@pytest.mark.asyncio
async def test_login_limit_throttles_repeated_attempts(session, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "login_rate_limit_max", 2)
    req = Request({
        "type": "http", "method": "POST", "path": "/api/v1/auth/login",
        "headers": [], "client": ("127.0.0.1", 9999), "query_string": b"",
    })
    await enforce_login_rate_limit(req, session)
    await enforce_login_rate_limit(req, session)
    with pytest.raises(RateLimitExceededError):
        await enforce_login_rate_limit(req, session)
