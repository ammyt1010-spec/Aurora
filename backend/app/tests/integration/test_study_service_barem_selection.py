import pytest

from app.core.exceptions import ValidationDomainError
from app.models.analytics_plan import AnalyticsPlan
from app.models.censopas import Barem
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
