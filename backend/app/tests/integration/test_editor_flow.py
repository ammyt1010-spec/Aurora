"""Flujo end-to-end del editor con variables fuera del árbol interno."""

from httpx import AsyncClient

from app.core.security import create_access_token


async def test_full_editor_flow(client: AsyncClient, seed_user) -> None:
    token = create_access_token(seed_user.id)
    headers = {"Authorization": f"Bearer {token}"}
    project = (
        await client.post(
            "/api/v1/projects",
            json={"owner_user_id": seed_user.id, "name": "Tesis de satisfacción académica", "project_type": "ACADEMIC"},
            headers=headers,
        )
    ).json()
    instrument = (
        await client.post(
            f"/api/v1/projects/{project['id']}/instruments",
            json={"owner_user_id": seed_user.id, "name": "Cuestionario", "is_system": False},
        )
    ).json()
    version = (
        await client.post(
            f"/api/v1/instruments/{instrument['id']}/versions",
            json={"version_code": "V1", "version_name": "Versión 1", "status": "DRAFT"},
        )
    ).json()

    empty_tree = (await client.get(f"/api/v1/instrument-versions/{version['id']}/tree")).json()
    assert empty_tree["variables"] == []

    variable_resp = await client.post(
        f"/api/v1/instrument-versions/{version['id']}/structure-variables",
        json={"code": "SATISFACCION", "name": "Satisfacción estudiantil", "role": "DEPENDENT"},
    )
    assert variable_resp.status_code == 201, variable_resp.text
    variable = variable_resp.json()

    dimension = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/constructs",
            json={"parent_id": variable["id"], "code": "D1", "name": "Satisfacción con la enseñanza", "construct_type": "DIMENSION"},
        )
    ).json()
    item = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/items",
            json={"code": "P1", "question_text": "¿Qué tan satisfecho está?", "question_type": "LIKERT"},
        )
    ).json()
    assert (
        await client.post(
            f"/api/v1/constructs/{dimension['id']}/items",
            json={"question_id": item["id"], "weight": 1, "scoring_direction": "DIRECT"},
        )
    ).status_code == 201

    direct_item = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/items",
            json={"code": "P2", "question_text": "¿Recomendaría el proyecto?", "question_type": "LIKERT"},
        )
    ).json()
    assert (
        await client.post(
            f"/api/v1/constructs/{variable['id']}/items",
            json={"question_id": direct_item["id"], "weight": 1, "scoring_direction": "DIRECT"},
        )
    ).status_code == 201

    tree = (await client.get(f"/api/v1/instrument-versions/{version['id']}/tree")).json()
    assert tree["editable"] is True
    assert len(tree["variables"]) == 1
    variable_tree = tree["variables"][0]
    assert variable_tree["name"] == "Satisfacción estudiantil"
    assert variable_tree["role"] == "DEPENDENT"
    assert len(variable_tree["direct_items"]) == 1
    assert len(variable_tree["dimensions"]) == 1
    assert len(variable_tree["dimensions"][0]["items"]) == 1

    rows = (
        await client.get(f"/api/v1/instrument-versions/{version['id']}/construct-matrix")
    ).json()["rows"]
    dimension_row = next(row for row in rows if row["item_code"] == "P1")
    direct_row = next(row for row in rows if row["item_code"] == "P2")
    assert dimension_row["research_variable_name"] == variable["name"]
    assert dimension_row["dimension_code"] == "D1"
    assert direct_row["research_variable_name"] == variable["name"]
    assert direct_row["dimension_code"] is None

    cloned = (
        await client.post(
            f"/api/v1/instruments/{instrument['id']}/versions/{version['id']}/clone",
            json={"version_code": "V2", "version_name": "Versión 2"},
        )
    ).json()
    cloned_tree = (
        await client.get(f"/api/v1/instrument-versions/{cloned['id']}/tree")
    ).json()
    assert len(cloned_tree["variables"]) == 1
    assert len(cloned_tree["variables"][0]["direct_items"]) == 1
    assert len(cloned_tree["variables"][0]["dimensions"][0]["items"]) == 1
