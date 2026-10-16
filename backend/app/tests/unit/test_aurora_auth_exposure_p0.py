"""Comprehensive unit and security tests for PR #5 (hardening/aurora-auth-exposure-p0)."""
import pytest
from unittest.mock import patch
from datetime import UTC, datetime

from app.core.config import Settings
from app.core.auth_cookie import add_session_cookies, is_request_secure, SESSION_COOKIE, CSRF_COOKIE
from app.core.network_security import is_direct_local_request
from app.core.security import create_access_token, access_token_fingerprint
from app.models.user import User
from app.models.revoked_token import RevokedAccessToken


class DummyRequest:
    def __init__(self, client_host="127.0.0.1", headers=None, url_scheme="http"):
        class Client:
            host = client_host
        class URL:
            scheme = url_scheme
        self.client = Client()
        self.headers = headers or {}
        self.url = URL()


# -----------------------------------------------------------------------------
# 1. Network Security and Demo Access Hardening
# -----------------------------------------------------------------------------

def test_is_direct_local_request_accepts_clean_loopback():
    req = DummyRequest(client_host="127.0.0.1", headers={"host": "127.0.0.1:8003"})
    assert is_direct_local_request(req) is True

    req_ipv6 = DummyRequest(client_host="::1", headers={"host": "localhost:5177"})
    assert is_direct_local_request(req_ipv6) is True


def test_is_direct_local_request_rejects_external_client():
    req = DummyRequest(client_host="203.0.113.19", headers={"host": "localhost:8003"})
    assert is_direct_local_request(req) is False


def test_is_direct_local_request_rejects_tunnel_headers():
    tunnel_headers = [
        {"cf-connecting-ip": "203.0.113.1"},
        {"cf-ray": "8293748293"},
        {"cf-visitor": '{"scheme":"https"}'},
        {"true-client-ip": "198.51.100.4"},
        {"x-envoy-external-address": "198.51.100.5"},
    ]
    for h in tunnel_headers:
        req = DummyRequest(client_host="127.0.0.1", headers={**h, "host": "127.0.0.1:8003"})
        assert is_direct_local_request(req) is False, f"Failed to reject header: {h}"


def test_is_direct_local_request_rejects_public_host():
    req = DummyRequest(client_host="127.0.0.1", headers={"host": "eventually-sheep-bearing-checks.trycloudflare.com"})
    assert is_direct_local_request(req) is False

    req2 = DummyRequest(client_host="127.0.0.1", headers={"x-forwarded-host": "aurora.pe"})
    assert is_direct_local_request(req2) is False


def test_is_direct_local_request_rejects_external_xff_or_real_ip():
    req = DummyRequest(client_host="127.0.0.1", headers={"x-forwarded-for": "127.0.0.1, 203.0.113.5"})
    assert is_direct_local_request(req) is False

    req2 = DummyRequest(client_host="127.0.0.1", headers={"x-real-ip": "198.51.100.9"})
    assert is_direct_local_request(req2) is False

    req3 = DummyRequest(client_host="127.0.0.1", headers={"forwarded": "for=192.0.2.60;proto=http"})
    assert is_direct_local_request(req3) is False

    req4 = DummyRequest(client_host="127.0.0.1", headers={"x-forwarded-proto": "https"})
    assert is_direct_local_request(req4) is False


def test_settings_rejects_demo_access_in_production_or_staging():
    with pytest.raises(ValueError, match="No se permite DEMO_ACCESS_ENABLED en entornos de producción o staging"):
        Settings(
            environment="production",
            demo_access_enabled=True,
            jwt_secret_key="a" * 50,
        )

    with pytest.raises(ValueError, match="No se permite DEMO_ACCESS_ENABLED en entornos de producción o staging"):
        Settings(
            environment="staging",
            demo_access_enabled=True,
            jwt_secret_key="a" * 50,
        )


def test_settings_rejects_demo_access_with_public_cors_origins():
    with pytest.raises(ValueError, match="CORS_ORIGINS contiene dominios públicos o HTTPS"):
        Settings(
            environment="development",
            demo_access_enabled=True,
            cors_origins=["https://aurora.pe", "http://localhost:5174"],
        )


# -----------------------------------------------------------------------------
# 2. HTTPS Secure Cookie Detection
# -----------------------------------------------------------------------------

def test_is_request_secure_direct_and_proxied():
    # Local HTTP
    req_http = DummyRequest(url_scheme="http", headers={})
    assert is_request_secure(req_http) is False

    # Direct HTTPS
    req_https = DummyRequest(url_scheme="https", headers={})
    assert is_request_secure(req_https) is True

    # Reverse proxy TLS termination
    req_proto = DummyRequest(url_scheme="http", headers={"x-forwarded-proto": "https"})
    assert is_request_secure(req_proto) is True

    # Cloudflare TLS termination
    req_cf = DummyRequest(url_scheme="http", headers={"cf-visitor": '{"scheme":"https"}'})
    assert is_request_secure(req_cf) is True


def test_add_session_cookies_sets_secure_flag_under_tls():
    from fastapi import Response
    resp = Response()
    req_tls = DummyRequest(url_scheme="http", headers={"x-forwarded-proto": "https"})
    add_session_cookies(resp, "test-token-jwt", req_tls)

    set_cookie_headers = [v for k, v in resp.raw_headers if k.lower() == b"set-cookie"]
    assert len(set_cookie_headers) == 2
    session_hdr = next(h.decode() for h in set_cookie_headers if "aurora_session=" in h.decode())
    assert "Secure" in session_hdr
    assert "samesite=strict" in session_hdr.lower()


# -----------------------------------------------------------------------------
# 3. Demo Login Endpoint Enforcement & Session Version
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_demo_login_rejected_from_public_tunnel(client):
    from app.core.config import get_settings
    fake_settings = get_settings().model_copy(update={"demo_access_enabled": True, "environment": "development"})
    with patch("app.api.v1.auth.get_settings", return_value=fake_settings):
        # Request with Cloudflare Tunnel header must be blocked even if proxy host is 127.0.0.1
        resp = await client.post(
            "/api/v1/auth/demo-login",
            headers={"CF-Connecting-IP": "203.0.113.19", "Host": "tunnel.trycloudflare.com"},
        )
        assert resp.status_code == 401
        assert "túneles o proxies" in resp.json()["message"]


@pytest.mark.asyncio
async def test_demo_login_respects_session_version_and_active_status(client, session):
    user = User(
        email="demo-user-sv@aurora.test",
        username="demo-user-sv",
        first_name="Supervisor",
        status="ACTIVE",
        session_version=2,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    from app.core.config import get_settings
    fake_settings = get_settings().model_copy(
        update={"demo_access_enabled": True, "demo_user_email": "demo-user-sv@aurora.test", "environment": "development"}
    )
    with patch("app.api.v1.auth.get_settings", return_value=fake_settings):
        resp = await client.post("/api/v1/auth/demo-login")
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        # Token must have sv=2
        from app.core.security import decode_access_token_claims
        claims = decode_access_token_claims(token)
        assert claims["sv"] == 2

        # Deactivated demo user must be rejected
        user.status = "DISABLED"
        await session.commit()
        resp_disabled = await client.post("/api/v1/auth/demo-login")
        assert resp_disabled.status_code == 401


# -----------------------------------------------------------------------------
# 4. Dual Credentials (Bearer + Cookie) Handling & Logout Revocation
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dual_credentials_matching_account_succeeds(client, session):
    user = User(email="dual-ok@aurora.test", username="dual-ok", status="ACTIVE")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token1 = create_access_token(user.id, user.session_version)
    token2 = create_access_token(user.id, user.session_version)

    client.cookies.set(SESSION_COOKIE, token1, path="/api/v1")
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "dual-ok@aurora.test"


@pytest.mark.asyncio
async def test_dual_credentials_conflicting_accounts_rejected(client, session):
    user_a = User(email="account-a@aurora.test", username="account-a", status="ACTIVE")
    user_b = User(email="account-b@aurora.test", username="account-b", status="ACTIVE")
    session.add_all([user_a, user_b])
    await session.commit()
    await session.refresh(user_a)
    await session.refresh(user_b)

    token_a = create_access_token(user_a.id, user_a.session_version)
    token_b = create_access_token(user_b.id, user_b.session_version)

    # Bearer is user A, but cookie is user B -> must reject with 401
    client.cookies.set(SESSION_COOKIE, token_b, path="/api/v1")
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 401
    assert "Conflicto de credenciales" in resp.json()["message"]


@pytest.mark.asyncio
async def test_logout_revokes_both_bearer_and_cookie_simultaneously(client, session):
    user = User(email="dual-logout@aurora.test", username="dual-logout", status="ACTIVE")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token_bearer = create_access_token(user.id, user.session_version)
    token_cookie = create_access_token(user.id, user.session_version)

    client.cookies.set(SESSION_COOKIE, token_cookie, path="/api/v1")
    client.cookies.set(CSRF_COOKIE, "csrf-token-123", path="/")

    # Call logout with both credentials present
    resp = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token_bearer}", "X-CSRF-Token": "csrf-token-123"},
    )
    assert resp.status_code == 204

    # Both tokens must be marked revoked in DB
    hash_bearer = access_token_fingerprint(token_bearer)
    hash_cookie = access_token_fingerprint(token_cookie)
    assert await session.get(RevokedAccessToken, hash_bearer) is not None
    assert await session.get(RevokedAccessToken, hash_cookie) is not None

    # Subsequent access with Bearer fails
    client.cookies.clear()
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_bearer}"})).status_code == 401

    # Subsequent access with Cookie fails
    client.cookies.set(SESSION_COOKIE, token_cookie, path="/api/v1")
    assert (await client.get("/api/v1/auth/me")).status_code == 401
