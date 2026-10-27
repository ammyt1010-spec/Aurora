import pytest

from app.core.exceptions import ValidationDomainError
from app.models.construct import Construct, ConstructItem
from app.models.analytics_plan import AnalyticsPlan
from app.models.censopas import Barem
from app.models.instrument import InstrumentVersion
from app.models.question import Question
from app.models.survey import Survey
from app.schemas.studies import StudyCreate
from app.services.study_service import StudyService


async def _prepare_censopas_study(session, project, user, version, metadata):
    project.project_type = "CENSO"
    project.metadata_ = metadata
    session.add(AnalyticsPlan(code="STANDARD", name="Standard", level=1, is_active=True))
    survey = Survey(
        project_id=project.id,
        instrument_version_id=version.id,
        created_by_user_id=user.id,
        name="Synthetic CENSOPAS study",
        survey_type="CENSO",
    )
    session.add(survey)
    await session.flush()
    return survey


def _study_payload(survey_id):
    return StudyCreate(
        survey_id=survey_id,
        name="Synthetic CENSOPAS study",
        study_type="CENSO",
        min_publishable_n=5,
    )


@pytest.mark.asyncio
async def test_explicit_barem_for_another_version_is_rejected_even_if_match_exists(
    session,
    seed_project,
    seed_user,
    seed_censopas_locked,
    seed_instrument_draft,
):
    _, version = seed_censopas_locked
    _, other_version = seed_instrument_draft
    matching = Barem(instrument_version_id=version.id, name="Matching candidate")
    configured = Barem(instrument_version_id=other_version.id, name="Configured mismatch")
    session.add_all([matching, configured])
    await session.flush()
    survey = await _prepare_censopas_study(
        session, seed_project, seed_user, version, {"barem_id": configured.id}
    )

    with pytest.raises(ValidationDomainError, match="no corresponde al formulario"):
        await StudyService(session).create(seed_project.id, _study_payload(survey.id))


@pytest.mark.asyncio
async def test_barem_is_not_inferred_when_project_has_no_explicit_configuration(
    session,
    seed_project,
    seed_user,
    seed_censopas_locked,
):
    _, version = seed_censopas_locked
    session.add(Barem(instrument_version_id=version.id, name="Available candidate"))
    await session.flush()
    survey = await _prepare_censopas_study(
        session, seed_project, seed_user, version, {}
    )

    study = await StudyService(session).create(seed_project.id, _study_payload(survey.id))

    assert study.barem_id is None


@pytest.mark.asyncio
async def test_explicit_matching_barem_is_preserved(
    session,
    seed_project,
    seed_user,
    seed_censopas_locked,
):
    _, version = seed_censopas_locked
    barem = Barem(instrument_version_id=version.id, name="Configured candidate")
    session.add(barem)
    await session.flush()
    survey = await _prepare_censopas_study(
        session, seed_project, seed_user, version, {"barem_id": barem.id}
    )

    study = await StudyService(session).create(seed_project.id, _study_payload(survey.id))

    assert study.barem_id == barem.id


@pytest.mark.asyncio
async def test_same_censopas_project_keeps_short_barem_and_assigns_medium_reference_by_version(
    client,
    session,
    seed_project,
    seed_user,
    seed_censopas_locked,
):
    instrument, short_version = seed_censopas_locked
    medium_version = InstrumentVersion(
        instrument_id=instrument.id,
        version_code="MEDIUM",
        version_name="Synthetic medium fixture",
        status="ACTIVE",
    )
    session.add(medium_version)
    await session.flush()

    medium_question = Question(
        instrument_version_id=medium_version.id,
        created_by_user_id=seed_user.id,
        code="MEDIUM_Q1",
        question_text="Synthetic scored fixture",
        question_type="LIKERT",
        research_role="ENDOGENOUS",
        is_scored=True,
    )
    medium_dimension = Construct(
        instrument_version_id=medium_version.id,
        code="MEDIUM_D1",
        name="Synthetic dimension",
        construct_type="DIMENSION",
        sort_order=1,
    )
    session.add_all([medium_question, medium_dimension])
    await session.flush()
    session.add(
        ConstructItem(
            construct_id=medium_dimension.id,
            question_id=medium_question.id,
            weight=1,
            item_role="SCORED",
            sort_order=1,
        )
    )

    short_barem = Barem(
        instrument_version_id=short_version.id,
        name="Synthetic SHORT reference",
        status="ACTIVE",
        metadata_={
            "barem_type": "REFERENCE",
            "official_equivalence": False,
            "project_id": seed_project.id,
        },
    )
    session.add_all(
        [
            short_barem,
            AnalyticsPlan(code="STANDARD", name="Standard", level=1, is_active=True),
        ]
    )
    seed_project.project_type = "CENSO"
    seed_project.metadata_ = {
        "instrument_version_id": short_version.id,
        "barem_id": None,
    }
    short_survey = Survey(
        project_id=seed_project.id,
        instrument_version_id=short_version.id,
        created_by_user_id=seed_user.id,
        name="Synthetic SHORT",
        survey_type="INSTRUMENT",
    )
    medium_survey = Survey(
        project_id=seed_project.id,
        instrument_version_id=medium_version.id,
        created_by_user_id=seed_user.id,
        name="Synthetic MEDIUM",
        survey_type="INSTRUMENT",
    )
    session.add_all([short_survey, medium_survey])
    await session.flush()
    seed_project.metadata_ = {
        "instrument_version_id": short_version.id,
        "barem_id": short_barem.id,
    }
    await session.commit()

    from app.core.security import create_access_token

    client.headers["Authorization"] = f"Bearer {create_access_token(seed_user.id)}"
    short_response = await client.post(
        f"/api/v1/projects/{seed_project.id}/studies",
        json={
            "survey_id": short_survey.id,
            "name": "Synthetic SHORT campaign",
            "study_type": "CENSO",
            "min_publishable_n": 5,
        },
    )
    assert short_response.status_code == 201, short_response.text
    short_study_id = short_response.json()["id"]
    assert short_response.json()["barem_id"] == short_barem.id

    medium_response = await client.post(
        f"/api/v1/projects/{seed_project.id}/studies",
        json={
            "survey_id": medium_survey.id,
            "name": "Synthetic MEDIUM campaign",
            "study_type": "CENSO",
            "min_publishable_n": 5,
        },
    )
    assert medium_response.status_code == 201, medium_response.text
    medium_barem_id = medium_response.json()["barem_id"]
    assert medium_barem_id != short_barem.id
    medium_barem = await session.get(Barem, medium_barem_id)
    assert medium_barem.instrument_version_id == medium_version.id
    assert medium_barem.metadata_["project_id"] == seed_project.id
    assert medium_barem.metadata_["barem_type"] == "REFERENCE"
    assert medium_barem.metadata_["official_equivalence"] is False
    assert medium_barem.barem_version == "REFERENCE-TERCILES-V1"

    # Simulate a retry: the same exact project/version reference is reused;
    # the already-created SHORT study and its barem remain untouched.
    from app.services.censopas_provisioning_service import CensopasProvisioningService

    reused = await CensopasProvisioningService(session)._ensure_reference_barem(
        seed_project, medium_version
    )
    assert reused.id == medium_barem_id
    existing_short = await StudyService(session).get(short_study_id)
    assert existing_short.barem_id == short_barem.id
    assert existing_short.instrument_version_id == short_version.id
