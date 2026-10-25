"""Only a matching draft questionnaire can receive an instrument link."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.study import Study
from app.models.survey import Survey


@pytest.mark.asyncio
@pytest.mark.parametrize("status, matching, expected", [
    ("OPEN", True, 409), ("CLOSED", True, 409), ("ARCHIVED", True, 409),
    ("DRAFT", False, 409), ("DRAFT", True, 200),
])
async def test_instrument_link_requires_matching_draft_survey(
    session, seed_project, seed_user, seed_censopas_locked, status, matching, expected,
):
    _, version = seed_censopas_locked
    survey = Survey(project_id=seed_project.id, created_by_user_id=seed_user.id,
                    instrument_version_id=version.id if matching else None,
                    name="Fixture questionnaire", survey_type="ACADEMIC", status="DRAFT")
    session.add(survey)
    await session.flush()
    study = Study(project_id=seed_project.id, survey_id=survey.id, name="Fixture study",
                  study_type="ACADEMIC", status=status)
    session.add(study)
    await session.commit()

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/studies/{study.id}/instruments/{version.id}",
                headers={"Authorization": f"Bearer {create_access_token(seed_user.id)}"},
            )
            assert response.status_code == expected
            await session.refresh(study)
            await session.refresh(survey)
            assert study.instrument_version_id == (version.id if expected == 200 else None)
            assert survey.instrument_version_id == (version.id if matching else None)
    finally:
        app.dependency_overrides.clear()
