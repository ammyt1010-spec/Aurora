"""Unit tests for active device session inventory, independent revocation, and privacy."""
from datetime import UTC, datetime, timedelta
import pytest
from sqlalchemy import select

from app.core.device_parser import anonymize_ip, parse_device_info
from app.models.audit import AuditLog
from app.models.user import User
from app.models.user_session import UserSession
from app.services.session_service import SessionService


def test_device_parser_and_anonymize_ip():
    # 1. Device and Browser detection
    chrome_win = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    res = parse_device_info(chrome_win)
    assert res["device_family"] == "Desktop"
    assert res["os_family"] == "Windows"
    assert res["browser_family"] == "Chrome"

    iphone_safari = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    res = parse_device_info(iphone_safari)
    assert res["device_family"] == "Mobile"
    assert res["os_family"] == "iOS"
    assert res["browser_family"] == "Safari"

    ipad_safari = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    res = parse_device_info(ipad_safari)
    assert res["device_family"] == "Tablet"
    assert res["os_family"] == "iOS"

    # 2. Privacy-preserving IP anonymization
    assert anonymize_ip("127.0.0.1") == "127.0.0.1"
    assert anonymize_ip("localhost") == "127.0.0.1"
    assert anonymize_ip("::1") == "127.0.0.1"
    assert anonymize_ip("190.237.45.120") == "190.237.45.***"
    assert anonymize_ip("2001:db8:85a3:8d3:1319:8a2e:370:7348") == "2001:db8:85a3::***"
    assert anonymize_ip(None) is None


@pytest.mark.asyncio
async def test_session_lifecycle_and_independent_revocation(session):
    # Setup test user
    user = User(
        email="session.test@empresa-a.pe",
        username="session_test_user",
        first_name="User",
        last_name="Test",
        status="ACTIVE",
        session_version=1,
    )
    session.add(user)
    await session.flush()

    service = SessionService(session)

    # 1. Create Device 1 Session (Desktop Chrome)
    token_1, sid_1 = await service.create_user_session(user)
    # 2. Create Device 2 Session (Mobile Safari)
    token_2, sid_2 = await service.create_user_session(user)
    await session.flush()

    # Verify both sessions are active in DB
    sessions_user = await service.list_user_sessions(user.id, current_sid=sid_1)
    assert len(sessions_user) == 2
    curr_s = next(s for s in sessions_user if s.session_id == sid_1)
    other_s = next(s for s in sessions_user if s.session_id == sid_2)
    assert curr_s.is_current is True
    assert other_s.is_current is False

    # 3. Verify audit log has USER_LOGIN entries
    audits = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.user_id == user.id, AuditLog.action == "USER_LOGIN"
            )
        )
    ).scalars().all()
    assert len(audits) == 2

    # 4. Revoke Device 2 independently
    revoked = await service.revoke_user_session(user.id, sid_2, reason="USER_REVOKED")
    assert revoked is True
    await session.flush()

    # Active sessions list should now only contain Device 1
    sessions_after = await service.list_user_sessions(user.id, current_sid=sid_1)
    assert len(sessions_after) == 1
    assert sessions_after[0].session_id == sid_1

    # Verify audit event USER_SESSION_REVOKED
    audit_rev = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.user_id == user.id,
                AuditLog.action == "USER_SESSION_REVOKED",
            )
        )
    ).scalars().first()
    assert audit_rev is not None
    assert audit_rev.entity_id == (await session.execute(select(UserSession.id).where(UserSession.session_id == sid_2))).scalar_one()
    assert "session_id" not in (audit_rev.after_data or {})


@pytest.mark.asyncio
async def test_api_session_management_and_isolation(client, session):
    # Create two users in different companies
    user_a = User(email="alice@company-a.pe", username="alice_a", status="ACTIVE", session_version=0)
    user_b = User(email="bob@company-b.pe", username="bob_b", status="ACTIVE", session_version=0)
    session.add_all([user_a, user_b])
    await session.commit()
    await session.refresh(user_a)
    await session.refresh(user_b)

    service = SessionService(session)
    token_a1, sid_a1 = await service.create_user_session(user_a)
    token_a2, sid_a2 = await service.create_user_session(user_a)
    token_b, sid_b = await service.create_user_session(user_b)
    await session.commit()

    # Alice lists her sessions: should see 2 sessions, none of Bob's
    resp = await client.get("/api/v1/auth/sessions", headers={"Authorization": f"Bearer {token_a1}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    sids = {s["session_id"] for s in data}
    assert sid_a1 in sids and sid_a2 in sids
    assert sid_b not in sids

    # Isolation test: Alice attempts to revoke Bob's session (must fail 404)
    resp_attack = await client.delete(
        f"/api/v1/auth/sessions/{sid_b}",
        headers={"Authorization": f"Bearer {token_a1}"},
    )
    assert resp_attack.status_code == 404

    # Bob's session is still completely valid
    resp_b_valid = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b_valid.status_code == 200

    # Alice revokes her session 2 (sid_a2)
    resp_rev = await client.delete(
        f"/api/v1/auth/sessions/{sid_a2}",
        headers={"Authorization": f"Bearer {token_a1}"},
    )
    assert resp_rev.status_code == 204

    # Request using revoked token_a2 MUST return 401
    resp_a2_blocked = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a2}"})
    assert resp_a2_blocked.status_code == 401

    # Alice's current session token_a1 MUST still return 200
    resp_a1_ok = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a1}"})
    assert resp_a1_ok.status_code == 200


@pytest.mark.asyncio
async def test_revoke_other_sessions_api(client, session):
    user = User(email="charlie@company.pe", username="charlie_c", status="ACTIVE", session_version=0)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    service = SessionService(session)
    token_1, sid_1 = await service.create_user_session(user)
    token_2, sid_2 = await service.create_user_session(user)
    token_3, sid_3 = await service.create_user_session(user)
    await session.commit()

    # Revoke other sessions from token_1
    resp = await client.delete("/api/v1/auth/sessions", headers={"Authorization": f"Bearer {token_1}"})
    assert resp.status_code == 200
    assert resp.json()["revoked_count"] == 2

    # Device 2 and Device 3 blocked
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_2}"})).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_3}"})).status_code == 401

    # Device 1 remains active
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_1}"})).status_code == 200


@pytest.mark.asyncio
async def test_cleanup_expired_sessions(session):
    user = User(email="cleanup@test.pe", username="cleanup_u", status="ACTIVE")
    session.add(user)
    await session.flush()

    now = datetime.now(UTC)
    # 1. Expired session (> 30 days old)
    old_expired = UserSession(
        user_id=user.id,
        session_id="expired_sid_1",
        expires_at=now - timedelta(days=35),
        created_at=now - timedelta(days=40),
        last_activity_at=now - timedelta(days=35),
    )
    # 2. Revoked session that is already expired
    revoked_expired = UserSession(
        user_id=user.id,
        session_id="revoked_expired_sid_2",
        expires_at=now - timedelta(hours=2),
        revoked_at=now - timedelta(hours=3),
        created_at=now - timedelta(days=1),
        last_activity_at=now - timedelta(hours=3),
    )
    # 3. Active session
    active = UserSession(
        user_id=user.id,
        session_id="active_sid_3",
        expires_at=now + timedelta(days=5),
        created_at=now,
        last_activity_at=now,
    )
    session.add_all([old_expired, revoked_expired, active])
    await session.flush()

    service = SessionService(session)
    purged_s, _ = await service.cleanup_expired_sessions()
    await session.flush()
    assert purged_s >= 2

    # Active session still exists
    rem = (await session.execute(select(UserSession).where(UserSession.session_id == "active_sid_3"))).scalar_one_or_none()
    assert rem is not None


@pytest.mark.asyncio
async def test_sid_token_without_db_session_fails_closed(client, session):
    from app.core.security import create_access_token
    user = User(email="missing-session@aurora.test", username="missing_session", status="ACTIVE", session_version=0)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    missing = create_access_token(user.id, user.session_version, session_id="a" * 43)
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {missing}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sid_token_must_match_owner_and_row_version(client, session):
    from app.core.security import create_access_token
    alice = User(email="sid-owner@aurora.test", username="sid_owner", status="ACTIVE", session_version=0)
    bob = User(email="sid-other@aurora.test", username="sid_other", status="ACTIVE", session_version=0)
    session.add_all([alice, bob])
    await session.commit()
    service = SessionService(session)
    _, sid = await service.create_user_session(alice)
    await session.commit()

    forged_owner = create_access_token(bob.id, bob.session_version, session_id=sid)
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_owner}"})).status_code == 401

    row = (await session.execute(select(UserSession).where(UserSession.session_id == sid))).scalar_one()
    row.session_version = 50
    await session.commit()
    mismatched_version = create_access_token(alice.id, alice.session_version, session_id=sid)
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {mismatched_version}"})).status_code == 401


@pytest.mark.asyncio
async def test_cleanup_restricted_to_configured_operator(client, session, monkeypatch):
    from app.core.config import get_settings
    user = User(email="non-operator@aurora.test", username="non_operator", status="ACTIVE")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    service = SessionService(session)
    token, _ = await service.create_user_session(user)
    await session.commit()
    endpoint = "/api/v1/auth/sessions/cleanup"
    # Nobody may perform a global purge when no operator is configured.
    resp = await client.post(endpoint, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    monkeypatch.setattr(
        "app.api.v1.sessions.get_settings",
        lambda: get_settings().model_copy(update={"session_maintenance_operator_user_id": user.id}),
    )
    ok = await client.post(endpoint, headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_pre_migration_token_cannot_revoke_all_modern_sessions(client, session):
    from app.core.security import create_access_token
    user = User(email="legacy-revoke@aurora.test", username="legacy_revoke", status="ACTIVE")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    service = SessionService(session)
    modern_token, modern_sid = await service.create_user_session(user)
    await session.commit()
    legacy_token = create_access_token(user.id, user.session_version)
    resp = await client.delete("/api/v1/auth/sessions", headers={"Authorization": f"Bearer {legacy_token}"})
    assert resp.status_code == 401
    still_active = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {modern_token}"})
    assert still_active.status_code == 200
