"""Real ASGI security regression: project IDOR, payload IDOR, CSRF."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.project import Project
from app.models.survey import Survey
from app.models.user import User


@pytest.mark.asyncio
async def test_live_authorization_rejects_other_tenant(
    session, seed_project, seed_user,
):
    outsider = User(email="tenant-isolation@aurora.test", username="tenant-guest", status="ACTIVE")
    session.add(outsider)
    await session.commit()
    await session.refresh(outsider)

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            url = f"/api/v1/projects/{seed_project.id}/studies"
            res = await client.get(url)
            assert res.status_code == 401, res.text
            res = await client.get(
                url, headers={"Authorization": f"Bearer {create_access_token(outsider.id)}"}
            )
            assert res.status_code == 403, res.text
            res = await client.get(
                url, headers={"Authorization": f"Bearer {create_access_token(seed_user.id)}"}
            )
            assert res.status_code == 200, res.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_live_payload_rejects_cross_project_survey(
    session, seed_project, seed_user,
):
    other = Project(owner_user_id=seed_user.id, name="Unrelated", project_type="ACADEMIC", status="DRAFT")
    session.add(other)
    await session.flush()
    survey = Survey(
        project_id=other.id, created_by_user_id=seed_user.id,
        name="Not allowed", survey_type="ACADEMIC", status="DRAFT",
    )
    session.add(survey)
    await session.commit()

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/projects/{seed_project.id}/studies",
                json={"survey_id": survey.id, "name": "Attempt", "study_type": "ACADEMIC"},
                headers={"Authorization": f"Bearer {create_access_token(seed_user.id)}"},
            )
            assert response.status_code == 403, response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_browser_cookie_requires_csrf_to_write(session, seed_project, seed_user):
    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={"aurora_session": create_access_token(seed_user.id), "aurora_csrf": "csrf-example"},
        ) as client:
            url = f"/api/v1/projects/{seed_project.id}"
            assert (await client.get(url)).status_code == 200
            denied = await client.patch(url, json={"name": "Forbidden"})
            assert denied.status_code == 403
            allowed = await client.patch(
                url, json={"name": "Authorized"},
                headers={"X-CSRF-Token": "csrf-example"},
            )
            assert allowed.status_code == 200, allowed.text
    finally:
        app.dependency_overrides.clear()
