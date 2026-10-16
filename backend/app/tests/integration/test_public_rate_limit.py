"""E-17: rate limit por IP sobre la creación de sesiones públicas.

`get_settings().public_session_rate_limit_max` es 10 por defecto (ventana de
60s); `ASGITransport` resuelve `request.client` al mismo valor fijo para
todas las requests del proceso de test, así que el cupo se comparte entre
todas las llamadas de este test (de ahí la fixture `_reset_public_rate_limit`
en conftest.py, autouse, que limpia el estado entre tests)."""

from httpx import AsyncClient


async def _build_open_study(client: AsyncClient, seed_user, seed_project, seed_instrument_draft):
    _instrument, version = seed_instrument_draft
    await client.post(
        f"/api/v1/instrument-versions/{version.id}/items",
        json={"code": "P1", "question_text": "P1", "question_type": "NUMBER"},
    )
    survey = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/surveys/from-instrument",
            json={
                "created_by_user_id": seed_user.id,
                "instrument_version_id": version.id,
                "name": "Encuesta rate limit",
            },
        )
    ).json()
    study = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/studies",
            json={"survey_id": survey["id"], "name": "Estudio rate limit", "study_type": "CUSTOM"},
        )
    ).json()
    await client.post(f"/api/v1/studies/{study['id']}/open")
    return study


async def test_public_session_creation_rate_limited(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft, monkeypatch
) -> None:
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "public_session_rate_limit_max", 10)
    study = await _build_open_study(client, seed_user, seed_project, seed_instrument_draft)

    for _ in range(10):
        resp = await client.post(
            f"/api/v1/public/studies/{study['public_id']}/response-sessions"
        )
        assert resp.status_code == 201, resp.text

    blocked_resp = await client.post(
        f"/api/v1/public/studies/{study['public_id']}/response-sessions"
    )
    assert blocked_resp.status_code == 429, blocked_resp.text
    assert blocked_resp.json()["error_code"] == "RATE_LIMIT_EXCEEDED"
