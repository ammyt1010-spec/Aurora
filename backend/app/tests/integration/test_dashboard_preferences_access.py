"""Prueba de extremo a extremo del almacenamiento de panel por empresa."""
import pytest

from app.core.security import create_access_token
from app.models.user import Organization


@pytest.mark.asyncio
async def test_preferences_are_isolated_by_organization(client, session, seed_user, seed_project):
    auth = {"Authorization": f"Bearer {create_access_token(seed_user.id)}"}
    org_id = seed_project.organization_id
    save = await client.put(
        f"/api/v1/dashboard-preferences/{org_id}",
        headers=auth,
        json={"widgets": ["summary", "ranking"], "density": "comfortable", "chart_mode": "heatmap"},
    )
    assert save.status_code == 200, save.text
    assert save.json()["widgets"] == ["summary", "ranking"]

    read = await client.get(f"/api/v1/dashboard-preferences/{org_id}", headers=auth)
    assert read.status_code == 200
    assert read.json()["density"] == "comfortable"

    unrelated = Organization(name="Empresa ajena", tax_id="20800000001")
    session.add(unrelated)
    await session.commit()
    await session.refresh(unrelated)

    denied = await client.get(f"/api/v1/dashboard-preferences/{unrelated.id}", headers=auth)
    assert denied.status_code == 403
    denied_save = await client.put(
        f"/api/v1/dashboard-preferences/{unrelated.id}",
        headers=auth, json={"widgets": ["summary"]},
    )
    assert denied_save.status_code == 403


@pytest.mark.asyncio
async def test_preferences_reject_invalid_payload(client, seed_user, seed_project):
    auth = {"Authorization": f"Bearer {create_access_token(seed_user.id)}"}
    response = await client.put(
        f"/api/v1/dashboard-preferences/{seed_project.organization_id}",
        headers=auth, json={"widgets": ["ranking", "ranking"]},
    )
    assert response.status_code == 422
