"""Baterías empresariales, aislamiento, revocación y acceso público."""
import pytest
from app.core.security import create_access_token
from app.models.survey import Survey
from app.models.study import Study


@pytest.mark.asyncio
async def test_bundle_multi_study_link_and_revocation(
    client, session, seed_project, seed_user, seed_instrument_draft,
):
    _, version = seed_instrument_draft
    survey = Survey(
        project_id=seed_project.id, instrument_version_id=version.id,
        created_by_user_id=seed_user.id, name="Formulario de prueba", survey_type="CUSTOM",
    )
    session.add(survey)
    await session.flush()
    studies = [
        Study(
            project_id=seed_project.id, survey_id=survey.id,
            instrument_version_id=version.id,
            study_type="CUSTOM", name="Evaluación " + str(index),
            status="OPEN", requires_invitation=False,
        )
        for index in [1, 2]
    ]
    session.add_all(studies)
    await session.commit()
    for item in studies:
        await session.refresh(item)

    auth = {"Authorization": f"Bearer {create_access_token(seed_user.id)}"}
    created = await client.post(
        f"/api/v1/projects/{seed_project.id}/bundles",
        headers=auth,
        json={"label": "Batería de pruebas", "study_ids": [item.id for item in studies]},
    )
    assert created.status_code == 201, created.text
    bundle = created.json()
    public = await client.get(f"/api/v1/public/bundles/{bundle['public_id']}")
    assert public.status_code == 200
    assert len(public.json()["evaluations"]) == 2

    revoked = await client.post(
        f"/api/v1/projects/{seed_project.id}/bundles/{bundle['id']}/revoke",
        headers=auth,
    )
    assert revoked.status_code == 200
    blocked = await client.get(f"/api/v1/public/bundles/{bundle['public_id']}")
    assert blocked.status_code == 404


@pytest.mark.asyncio
async def test_multidisciplinary_campaign_keeps_own_version_in_censopas_project(
    client, session, seed_project, seed_user, seed_instrument_draft,
):
    _, version = seed_instrument_draft
    seed_project.project_type = "CENSO"
    # Deliberately different CENSOPAS version/barem: must not leak into research.
    seed_project.metadata_ = {"instrument_version_id": version.id + 1000, "barem_id": 99999}
    survey = Survey(project_id=seed_project.id, instrument_version_id=version.id,
                    created_by_user_id=seed_user.id, name="Synthetic ergonomics", survey_type="INSTRUMENT")
    session.add(survey)
    await session.commit()
    created = await client.post(f"/api/v1/projects/{seed_project.id}/studies", json={
        "survey_id": survey.id, "name": "Independent research", "study_type": "RESEARCH",
    })
    assert created.status_code == 201, created.text
    assert created.json()["instrument_version_id"] == version.id
    assert created.json()["study_type"] == "RESEARCH"
    assert created.json()["barem_id"] is None
    assert created.json()["status"] == "DRAFT"
    # Existing CENSOPAS mismatch guard still rejects a wrongly paired survey.
    censopas = await client.post(f"/api/v1/projects/{seed_project.id}/studies", json={
        "survey_id": survey.id, "name": "Incorrect CENSOPAS pairing", "study_type": "CENSO",
    })
    assert censopas.status_code == 422
