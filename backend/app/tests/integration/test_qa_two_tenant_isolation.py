"""Authorization proof with two existing organizations, projects and studies.

Uses the in-memory database and real auth guards; no network or live credentials.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.project import Project
from app.models.study import Study
from app.models.survey import Survey
from app.models.user import Organization, OrganizationMembership, User


@pytest.mark.asyncio
async def test_two_existing_tenants_cannot_read_or_report_each_others_data(session, seed_project, seed_user):
    other_user = User(email="other-tenant@isolated.example", username="other-tenant", status="ACTIVE")
    other_org = Organization(name="Isolated other organization", tax_id="20987654321")
    session.add_all([other_user, other_org])
    await session.flush()
    session.add(OrganizationMembership(organization_id=other_org.id, user_id=other_user.id, role_code="OWNER"))
    other_project = Project(owner_user_id=other_user.id, organization_id=other_org.id,
                            name="Other tenant project", project_type="ACADEMIC", status="DRAFT")
    session.add(other_project)
    await session.flush()
    studies = []
    for project, user in ((seed_project, seed_user), (other_project, other_user)):
        survey = Survey(project_id=project.id, created_by_user_id=user.id,
                        name="Isolated survey", survey_type="ACADEMIC", status="DRAFT")
        session.add(survey)
        await session.flush()
        study = Study(project_id=project.id, survey_id=survey.id, name="Isolated study", study_type="ACADEMIC")
        session.add(study)
        await session.flush()
        studies.append(study)
    await session.commit()
    assert seed_project.organization_id is not None
    assert seed_project.organization_id != other_project.organization_id

    async def db_override():
        yield session

    # No require_business_access/get_current_user overrides: exercise real guards.
    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            projects = [seed_project, other_project]
            for index, user in enumerate((seed_user, other_user)):
                headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}
                own_project, other_project = projects[index], projects[1 - index]
                own_study, other_study = studies[index], studies[1 - index]
                assert (await client.get(f"/api/v1/projects/{own_project.id}", headers=headers)).status_code == 200
                assert (await client.get(f"/api/v1/studies/{own_study.id}", headers=headers)).status_code == 200
                for suffix in ("", "/telemetry"):
                    response = await client.get(f"/api/v1/projects/{other_project.id}{suffix}", headers=headers)
                    assert response.status_code in (403, 404)
                response = await client.post(f"/api/v1/studies/{other_study.id}/reports/preview",
                                             headers=headers, json={"report_mode": "PROVISIONAL"})
                assert response.status_code in (403, 404)
    finally:
        app.dependency_overrides.clear()
