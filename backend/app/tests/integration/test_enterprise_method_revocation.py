"""An OPEN enterprise campaign cannot reuse revoked catalog authorization."""
import pytest

from app.core.security import create_access_token
from app.models.construct import Construct
from app.models.study import Study
from app.models.survey import Survey
from app.services.study_service import StudyService


@pytest.mark.asyncio
@pytest.mark.parametrize("target, revoked", [
    ("instrument", "ARCHIVED"), ("instrument", "DRAFT"),
    ("version", "LOCKED"), ("version", "DRAFT"),
    ("scoring", "NOT_CONFIGURED"),
])
async def test_revocation_blocks_existing_enterprise_links(
    client, session, seed_project, seed_user, seed_instrument_draft, target, revoked,
):
    instrument, version = seed_instrument_draft
    seed_project.project_type = "RESEARCH"  # Real organization-backed enterprise fixture.
    instrument.organization_id = seed_project.organization_id
    instrument.status = "AUTHORIZED"
    version.status = "ACTIVE"
    version.scoring_status = "CONFIGURED"
    session.add(Construct(instrument_version_id=version.id, code="DIM", name="Fixture dimension", construct_type="DIMENSION"))
    survey = Survey(project_id=seed_project.id, instrument_version_id=version.id,
                    created_by_user_id=seed_user.id, name="Fixture", survey_type="INSTRUMENT")
    session.add(survey)
    await session.flush()
    studies = [Study(project_id=seed_project.id, survey_id=survey.id, instrument_version_id=version.id,
                     study_type="RESEARCH", name=f"Enterprise {index}", status="DRAFT") for index in range(2)]
    session.add_all(studies)
    await session.commit()
    for study in studies:
        await StudyService(session).open(study.id)
    auth = {"Authorization": f"Bearer {create_access_token(seed_user.id)}"}
    url = f"/api/v1/projects/{seed_project.id}/bundles"
    payload = {"label": "Authorized battery", "study_ids": [study.id for study in studies]}
    created = await client.post(url, headers=auth, json=payload)
    assert created.status_code == 201, created.text
    public_url = f"/api/v1/public/bundles/{created.json()['public_id']}"
    survey_url = f"/api/v1/public/studies/{studies[0].public_id}"
    assert (await client.get(public_url)).status_code == 200
    assert (await client.get(survey_url)).status_code == 200
    if target == "scoring":
        version.scoring_status = revoked
    else:
        setattr(instrument if target == "instrument" else version, "status", revoked)
    await session.commit()
    assert (await client.post(url, headers=auth, json=payload)).status_code == 422
    assert (await client.get(public_url)).status_code == 404
    assert (await client.get(survey_url)).status_code == 404
    assert (await client.post(survey_url + "/response-sessions", json={})).status_code == 404


@pytest.mark.asyncio
async def test_official_locked_version_allowed_but_archived_instrument_not(
    session, seed_project, seed_user, seed_censopas_locked,
):
    from app.core.exceptions import ValidationDomainError
    instrument, version = seed_censopas_locked
    seed_project.project_type = "RESEARCH"
    version.status = "LOCKED"
    study = Study(project_id=seed_project.id, survey_id=1, instrument_version_id=version.id,
                  study_type="RESEARCH", name="Official", status="OPEN", settings={})
    await session.flush()
    await StudyService(session).require_current_enterprise_method(study)
    instrument.status = "ARCHIVED"
    await session.flush()
    with pytest.raises(ValidationDomainError):
        await StudyService(session).require_current_enterprise_method(study)
