"""Access tokens remain invalid after logout, even through a different request."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token, decode_access_token
from app.models.user import User


def test_access_tokens_are_unique_even_when_minted_in_the_same_second():
    first = create_access_token(42)
    second = create_access_token(42)
    assert first != second
    assert decode_access_token(first) == decode_access_token(second) == 42


@pytest.mark.asyncio
async def test_bearer_logout_is_revoked_server_side(client, session):
    user = User(email="logout@aurora.test", username="logout-user", status="ACTIVE")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    before = await client.get("/api/v1/auth/me", headers=headers)
    assert before.status_code == 200

    signed_out = await client.post("/api/v1/auth/logout", headers=headers)
    assert signed_out.status_code == 204

    after = await client.get("/api/v1/auth/me", headers=headers)
    assert after.status_code == 401

    fresh = create_access_token(user.id)
    assert fresh != token
    still_active = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fresh}"})
    assert still_active.status_code == 200


@pytest.mark.asyncio
async def test_cookie_logout_invalidates_stolen_cookie_token(client, session):
    user = User(email="cookie-logout@aurora.test", username="cookie-logout", status="ACTIVE")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(user.id)
    # Set the browser cookies exactly as the login endpoint does.
    from app.core.auth_cookie import add_session_cookies
    from fastapi import Response
    response = Response()
    add_session_cookies(response, token)
    cookie_headers = response.headers.getlist("set-cookie")
    from http.cookies import SimpleCookie
    cookies = SimpleCookie()
    for value in cookie_headers:
        cookies.load(value)
    csrf = cookies["aurora_csrf"].value
    client.cookies.set("aurora_session", token, path="/api/v1")
    client.cookies.set("aurora_csrf", csrf, path="/")

    assert (await client.get("/api/v1/auth/me")).status_code == 200
    logout = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout.status_code == 204
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401


@pytest.mark.asyncio
async def test_csrf_failure_does_not_revoke_valid_cookie(client, session):
    user = User(email="csrf-logout@aurora.test", username="csrf-logout", status="ACTIVE")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    token = create_access_token(user.id)
    client.cookies.set("aurora_session", token, path="/api/v1")
    client.cookies.set("aurora_csrf", "csrf-secret", path="/")
    denied = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "invalid"})
    assert denied.status_code == 403
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 200
