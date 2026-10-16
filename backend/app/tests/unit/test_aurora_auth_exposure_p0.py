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


# -----------------------------------------------------------------------------
# 5. Additional Bloque C & Bloque E Hardening Tests
# -----------------------------------------------------------------------------

def test_is_direct_local_request_rejects_0_0_0_0():
    """0.0.0.0 es INADDR_ANY y nunca debe ser aceptado como loopback."""
    # Client IP es 0.0.0.0
    req_ip = DummyRequest(client_host="0.0.0.0", headers={"host": "localhost:8003"})
    assert is_direct_local_request(req_ip) is False

    # Host es 0.0.0.0
    req_host = DummyRequest(client_host="127.0.0.1", headers={"host": "0.0.0.0:8003"})
    assert is_direct_local_request(req_host) is False

    # X-Forwarded-For contiene 0.0.0.0
    req_xff = DummyRequest(client_host="127.0.0.1", headers={"x-forwarded-for": "0.0.0.0", "host": "localhost:8003"})
    assert is_direct_local_request(req_xff) is False


def test_is_direct_local_request_rejects_via_and_forwarded_proxies():
    """Rechaza peticiones que incluyen encabezados Via, Forwarded o X-Forwarded-*."""
    req_via = DummyRequest(client_host="127.0.0.1", headers={"via": "1.1 proxy.corp.local", "host": "127.0.0.1:8003"})
    assert is_direct_local_request(req_via) is False

    req_fwd = DummyRequest(
        client_host="127.0.0.1",
        headers={"x-forwarded-server": "nginx.internal", "host": "127.0.0.1:8003"},
    )
    assert is_direct_local_request(req_fwd) is False


def test_is_direct_local_request_rejects_external_origin_and_referer():
    """Detecta proxies que reescriben Host a localhost pero mantienen Origin o Referer externo."""
    req_origin = DummyRequest(
        client_host="127.0.0.1",
        headers={"host": "localhost:8003", "origin": "https://external-tunnel.trycloudflare.com"},
    )
    assert is_direct_local_request(req_origin) is False

    req_ref = DummyRequest(
        client_host="127.0.0.1",
        headers={"host": "localhost:8003", "referer": "https://attacker.example.org/dashboard"},
    )
    assert is_direct_local_request(req_ref) is False


def test_settings_rejects_demo_access_in_unauthorized_env():
    with pytest.raises(ValueError, match="Solo está permitido en desarrollo local aislado"):
        Settings(
            environment="qa",
            demo_access_enabled=True,
            jwt_secret_key="b" * 50,
        )


def test_settings_rejects_demo_access_with_0_0_0_0_cors():
    with pytest.raises(ValueError, match="No se permite DEMO_ACCESS_ENABLED con 0.0.0.0 en CORS_ORIGINS"):
        Settings(
            environment="development",
            demo_access_enabled=True,
            cors_origins=["http://0.0.0.0:5174"],
        )


@pytest.mark.asyncio
async def test_stale_cookie_with_new_bearer_rejected(client, session):
    """Una cookie con versión de sesión anterior (stale) es rechazada incluso si el Bearer es nuevo."""
    user = User(email="stale-test@aurora.test", username="stale-test", status="ACTIVE", session_version=2)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    new_bearer = create_access_token(user.id, session_version=2)
    stale_cookie = create_access_token(user.id, session_version=1)

    client.cookies.set(SESSION_COOKIE, stale_cookie, path="/api/v1")
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_bearer}"})
    assert resp.status_code == 401
    assert "cookie fue invalidada" in resp.json()["message"]


@pytest.mark.asyncio
async def test_stale_bearer_with_new_cookie_rejected(client, session):
    """Un token Bearer con versión de sesión anterior es rechazado incluso si la cookie es nueva."""
    user = User(email="stale-b-test@aurora.test", username="stale-b-test", status="ACTIVE", session_version=2)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    stale_bearer = create_access_token(user.id, session_version=1)
    new_cookie = create_access_token(user.id, session_version=2)

    client.cookies.set(SESSION_COOKIE, new_cookie, path="/api/v1")
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {stale_bearer}"})
    assert resp.status_code == 401
    assert "Bearer fue invalidada" in resp.json()["message"]


@pytest.mark.asyncio
async def test_two_devices_same_account_global_logout(client, session):
    """Dos dispositivos con la misma cuenta: un logout global invalida a ambos."""
    user = User(email="twodev@aurora.test", username="twodev", status="ACTIVE", session_version=1)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token_dev1 = create_access_token(user.id, session_version=1)
    token_dev2 = create_access_token(user.id, session_version=1)

    # Ambos dispositivos acceden exitosamente
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_dev1}"})).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_dev2}"})).status_code == 200

    # Dispositivo 1 ejecuta logout_all
    resp_logout_all = await client.post("/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {token_dev1}"})
    assert resp_logout_all.status_code == 204

    # Dispositivo 1 queda revocado
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_dev1}"})).status_code == 401

    # Dispositivo 2 queda invalidado por version de sesion
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_dev2}"})).status_code == 401


@pytest.mark.asyncio
async def test_two_different_companies_isolation(client, session):
    """Acciones de cierre de sesión en Empresa A no afectan la sesión de Empresa B."""
    user_a = User(email="owner-a@corp-a.test", username="owner-a", status="ACTIVE", session_version=1)
    user_b = User(email="owner-b@corp-b.test", username="owner-b", status="ACTIVE", session_version=1)
    session.add_all([user_a, user_b])
    await session.commit()
    await session.refresh(user_a)
    await session.refresh(user_b)

    token_a = create_access_token(user_a.id, session_version=1)
    token_b = create_access_token(user_b.id, session_version=1)

    # Dispositivo A ejecuta logout individual
    resp_logout_a = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_logout_a.status_code == 204

    # Token A queda revocado
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})).status_code == 401

    # Token B sigue 100% activo y funcional
    resp_b = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    assert resp_b.json()["email"] == "owner-b@corp-b.test"


@pytest.mark.asyncio
async def test_csrf_protection_enforced_when_cookie_present(client, session):
    """Petición mutante (POST) con cookie de sesión pero sin encabezado X-CSRF-Token es rechazada con 403."""
    user = User(email="csrf-test@aurora.test", username="csrf-test", status="ACTIVE", session_version=1)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(user.id, session_version=1)
    client.cookies.set(SESSION_COOKIE, token, path="/api/v1")
    client.cookies.set(CSRF_COOKIE, "valid-csrf-token", path="/")

    # POST sin header CSRF -> 403
    resp_no_csrf = await client.post("/api/v1/auth/logout")
    assert resp_no_csrf.status_code == 403

    # POST con header CSRF correcto -> 204
    resp_with_csrf = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "valid-csrf-token"})
    assert resp_with_csrf.status_code == 204
