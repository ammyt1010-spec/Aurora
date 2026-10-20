from sqlalchemy import select

from app.models.question import Question
from app.models.survey import SurveyQuestion
from app.services.censopas_provisioning_service import CensopasProvisioningService


async def test_provisioned_survey_includes_all_instrument_questions_and_repairs_missing_links(
    session, seed_project, seed_instrument_draft
) -> None:
    _, version = seed_instrument_draft
    profile = Question(
        instrument_version_id=version.id,
        code="PROFILE",
        question_text="Área de trabajo",
        question_type="TEXT",
        research_role="EXOGENOUS",
        sort_order=1,
    )
    scored = Question(
        instrument_version_id=version.id,
        code="SCORED",
        question_text="¿Recibes apoyo en el trabajo?",
        question_type="LIKERT",
        research_role="ENDOGENOUS",
        is_scored=True,
        sort_order=2,
    )
    session.add_all([profile, scored])
    await session.flush()

    service = CensopasProvisioningService(session)
    survey = await service._ensure_survey(seed_project, version)
    links = list((await session.execute(
        select(SurveyQuestion).where(SurveyQuestion.survey_id == survey.id)
    )).scalars().all())
    assert {link.question_id for link in links} == {profile.id, scored.id}

    await session.delete(next(link for link in links if link.question_id == scored.id))
    await session.flush()
    same_survey = await service._ensure_survey(seed_project, version)
    assert same_survey.id == survey.id
    repaired = list((await session.execute(
        select(SurveyQuestion).where(SurveyQuestion.survey_id == survey.id)
    )).scalars().all())
    assert {link.question_id for link in repaired} == {profile.id, scored.id}
