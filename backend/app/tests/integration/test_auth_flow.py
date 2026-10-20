"""Flujo de autenticación propia de Colmena (registro/login/sesión)."""

from httpx import AsyncClient


async def test_register_login_and_me(client: AsyncClient) -> None:
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ana@colmena.dev",
            "username": "ana",
            "password": "supersecret123",
            "first_name": "Ana",
        },
    )
    assert register_resp.status_code == 201, register_resp.text
    user = register_resp.json()
    assert user["email"] == "ana@colmena.dev"
    assert "password" not in user

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "ana@colmena.dev", "password": "supersecret123"}
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    assert login_resp.json()["token_type"] == "bearer"

    me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "ana"


async def test_login_wrong_password_rejected(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "b@colmena.dev", "username": "b", "password": "correcthorse123"},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "b@colmena.dev", "password": "wrongpassword"}
    )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "AUTHENTICATION_ERROR"


async def test_duplicate_email_rejected(client: AsyncClient) -> None:
    payload = {"email": "dup@colmena.dev", "username": "dup1", "password": "supersecret123"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@colmena.dev", "username": "dup2", "password": "supersecret123"},
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "CONFLICT"


async def test_me_without_token_rejected(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_demo_login_uses_isolated_demo_user(client: AsyncClient, seed_user) -> None:
    response = await client.post("/api/v1/auth/demo-login")
    assert response.status_code == 200, response.text

    token = response.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["id"] != seed_user.id
    assert me.json()["first_name"] == "Demo Aurora"
