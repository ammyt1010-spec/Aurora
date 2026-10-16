"""Global logout invalidates all prior JWTs without affecting other accounts."""
import pytest
import jwt

from app.core.config import get_settings
from app.core.participant_tokens import create_participant_token, verify_participant_token
from app.core.security import create_access_token
from app.models.user import User


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_logout_all_invalidates_two_devices_and_preserves_other_users(client, session):
    user = User(email="all-devices@aurora.test", username="all-devices", status="ACTIVE")
    other = User(email="other-device@aurora.test", username="other-device", status="ACTIVE")
    session.add_all([user, other])
    await session.commit()
    await session.refresh(user)
    await session.refresh(other)

    first = create_access_token(user.id, user.session_version)
    second = create_access_token(user.id, user.session_version)
    outsider = create_access_token(other.id, other.session_version)
    assert (await client.get("/api/v1/auth/me", headers=headers(first))).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=headers(second))).status_code == 200

    response = await client.post("/api/v1/auth/logout-all", headers=headers(first))
    assert response.status_code == 204
    assert (await client.get("/api/v1/auth/me", headers=headers(first))).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=headers(second))).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=headers(outsider))).status_code == 200

    await session.refresh(user)
    assert user.session_version == 1
    new_token = create_access_token(user.id, user.session_version)
    assert (await client.get("/api/v1/auth/me", headers=headers(new_token))).status_code == 200
    # No token from the previous session version may increment the counter.
    assert (await client.post("/api/v1/auth/logout-all", headers=headers(second))).status_code == 401


@pytest.mark.asyncio
async def test_logout_all_enforces_cookie_csrf(client, session):
    user = User(email="cookie-global@aurora.test", username="cookie-global", status="ACTIVE")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    token = create_access_token(user.id, 0)
    client.cookies.set("aurora_session", token, path="/api/v1")
    client.cookies.set("aurora_csrf", "csrf-protected", path="/")

    response = await client.post("/api/v1/auth/logout-all", headers={"X-CSRF-Token": "bad"})
    assert response.status_code == 403
    assert (await client.get("/api/v1/auth/me", headers=headers(token))).status_code == 200

    response = await client.post("/api/v1/auth/logout-all", headers={"X-CSRF-Token": "csrf-protected"})
    assert response.status_code == 204
    assert (await client.get("/api/v1/auth/me", headers=headers(token))).status_code == 401


@pytest.mark.asyncio
async def test_legacy_jwt_also_invalidated_and_survey_capabilities_unaffected(client, session):
    user = User(email="legacy-session@aurora.test", username="legacy-session", status="ACTIVE")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    settings = get_settings()
    # A valid signed pre-migration token has no sv claim.
    current = create_access_token(user.id, 0)
    old_claims = jwt.decode(current, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    old_claims.pop("sv")
    legacy = jwt.encode(old_claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    assert (await client.get("/api/v1/auth/me", headers=headers(legacy))).status_code == 200
    participant = create_participant_token(123)
    verify_participant_token(participant, 123)

    assert (await client.post("/api/v1/auth/logout-all", headers=headers(legacy))).status_code == 204
    assert (await client.get("/api/v1/auth/me", headers=headers(legacy))).status_code == 401
    verify_participant_token(participant, 123)


@pytest.mark.asyncio
async def test_invalid_session_version_claim_is_rejected(client, session):
    user = User(email="wrong-version@aurora.test", username="wrong-version", status="ACTIVE")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    settings = get_settings()
    valid = create_access_token(user.id, 0)
    claims = jwt.decode(valid, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    claims["sv"] = "0"
    token = jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    assert (await client.get("/api/v1/auth/me", headers=headers(token))).status_code == 401
