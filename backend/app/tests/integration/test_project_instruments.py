from httpx import AsyncClient

from app.core.security import create_access_token


async def test_project_can_own_and_list_multiple_instruments(
    client: AsyncClient, seed_user, seed_project
) -> None:
    first = await client.post(
        f"/api/v1/projects/{seed_project.id}/instruments",
        json={"owner_user_id": seed_user.id, "name": "Satisfacción académica"},
    )
    second = await client.post(
        f"/api/v1/projects/{seed_project.id}/instruments",
        json={"owner_user_id": seed_user.id, "name": "Bienestar estudiantil"},
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["project_id"] == seed_project.id
    assert second.json()["project_id"] == seed_project.id

    response = await client.get(f"/api/v1/projects/{seed_project.id}/instruments")
    assert response.status_code == 200, response.text
    assert {item["name"] for item in response.json()["items"]} == {
        "Satisfacción académica",
        "Bienestar estudiantil",
    }


async def test_instrument_from_another_project_cannot_create_survey(
    client: AsyncClient, seed_user, seed_project
) -> None:
    token = create_access_token(seed_user.id)
    headers = {"Authorization": f"Bearer {token}"}
    other_project = (
        await client.post(
            "/api/v1/projects",
            json={
                "owner_user_id": seed_user.id,
                "name": "Otro proyecto",
                "project_type": "ACADEMIC",
            },
            headers=headers,
        )
    ).json()
    instrument = (
        await client.post(
            f"/api/v1/projects/{other_project['id']}/instruments",
            json={"owner_user_id": seed_user.id, "name": "Instrumento ajeno"},
        )
    ).json()
    version = (
        await client.post(
            f"/api/v1/instruments/{instrument['id']}/versions",
            json={"version_code": "v1"},
        )
    ).json()
    await client.post(
        f"/api/v1/instrument-versions/{version['id']}/items",
        json={"code": "P1", "question_text": "Pregunta", "question_type": "TEXT"},
    )

    response = await client.post(
        f"/api/v1/projects/{seed_project.id}/surveys/from-instrument",
        json={
            "created_by_user_id": seed_user.id,
            "instrument_version_id": version["id"],
            "name": "No permitido",
        },
    )
    assert response.status_code == 422
