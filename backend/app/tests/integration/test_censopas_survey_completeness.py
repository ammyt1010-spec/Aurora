"""Opening CENSOPAS studies must snapshot the complete item set for a version."""

import pytest
from sqlalchemy import func, select

from app.core.exceptions import ValidationDomainError
from app.models.question import Question
from app.models.study import Study, StudySnapshot
from app.models.survey import Survey, SurveyQuestion
from app.services.study_service import StudyService


def _question(version_id: int, code: str, *, is_scored: bool = False) -> Question:
    return Question(
        instrument_version_id=version_id,
        code=code,
        question_text=f"Synthetic item {code}",
        question_type="LIKERT",
        is_scored=is_scored,
        sort_order=int(code.removeprefix("Q")) if code.startswith("Q") else None,
    )


async def _study_with_survey(
    session,
    project,
    user,
    survey_version_id: int,
    linked_questions: list[Question],
    *,
    study_version_id: int | None = None,
):
    survey = Survey(
        project_id=project.id,
        created_by_user_id=user.id,
        instrument_version_id=survey_version_id,
        name="Synthetic CENSOPAS survey",
        survey_type="CENSO",
    )
    session.add(survey)
    await session.flush()
    for index, question in enumerate(linked_questions):
        session.add(
            SurveyQuestion(
                survey_id=survey.id,
                question_id=question.id,
                sort_order=index,
            )
        )

    study = Study(
        project_id=project.id,
        survey_id=survey.id,
        instrument_version_id=(
            survey_version_id if study_version_id is None else study_version_id
        ),
        name="Synthetic QA study",
        study_type="CENSO",
        status="DRAFT",
        min_publishable_n=5,
    )
    session.add(study)
    await session.commit()
    return study, survey


@pytest.mark.asyncio
async def test_open_rejects_censopas_survey_missing_scored_version_items(
    session, seed_project, seed_user, seed_censopas_locked
):
    _, version = seed_censopas_locked
    scored = _question(version.id, "Q1", is_scored=True)
    contextual = _question(version.id, "Q2")
    extra_scored = _question(version.id, "Q3", is_scored=True)
    session.add_all([scored, contextual, extra_scored])
    await session.flush()
    study, _ = await _study_with_survey(
        session,
        seed_project,
        seed_user,
        version.id,
        [contextual],
    )
    study_id = study.id

    with pytest.raises(ValidationDomainError, match="faltan 2 y hay 0"):
        await StudyService(session).open(study_id)

    await session.rollback()
    snapshot_count = await session.scalar(
        select(func.count(StudySnapshot.id)).where(StudySnapshot.study_id == study_id)
    )
    assert snapshot_count == 0


@pytest.mark.asyncio
async def test_open_rejects_same_count_but_different_censopas_question_id_set(
    session, seed_project, seed_user, seed_censopas_locked, seed_instrument_draft
):
    _, version = seed_censopas_locked
    _, other_version = seed_instrument_draft
    expected_one = _question(version.id, "Q1")
    expected_two = _question(version.id, "Q2")
    foreign_question = _question(other_version.id, "Q9")
    session.add_all([expected_one, expected_two, foreign_question])
    await session.flush()
    study, _ = await _study_with_survey(
        session,
        seed_project,
        seed_user,
        version.id,
        [expected_one, foreign_question],
    )

    with pytest.raises(ValidationDomainError, match="faltan 1 y hay 1"):
        await StudyService(session).open(study.id)


@pytest.mark.asyncio
async def test_open_rejects_censopas_survey_when_study_uses_another_version(
    session, seed_project, seed_user, seed_censopas_locked, seed_instrument_draft
):
    _, version = seed_censopas_locked
    _, other_version = seed_instrument_draft
    first = _question(version.id, "Q1")
    second = _question(version.id, "Q2")
    session.add_all([first, second])
    await session.flush()
    study, _ = await _study_with_survey(
        session,
        seed_project,
        seed_user,
        version.id,
        [first, second],
        study_version_id=other_version.id,
    )

    with pytest.raises(ValidationDomainError, match="misma versión"):
        await StudyService(session).open(study.id)


@pytest.mark.asyncio
async def test_open_accepts_complete_censopas_survey_and_snapshots_all_items(
    session, seed_project, seed_user, seed_censopas_locked
):
    _, version = seed_censopas_locked
    questions = [_question(version.id, "Q1"), _question(version.id, "Q2")]
    session.add_all(questions)
    await session.flush()
    study, _ = await _study_with_survey(
        session, seed_project, seed_user, version.id, questions
    )

    opened = await StudyService(session).open(study.id)

    assert opened.status == "OPEN"
    snapshot = await session.scalar(
        select(StudySnapshot).where(StudySnapshot.study_id == study.id)
    )
    assert len(snapshot.snapshot_data["survey"]["questions"]) == 2


@pytest.mark.asyncio
async def test_open_does_not_block_intentionally_partial_generic_survey(
    session, seed_project, seed_user, seed_instrument_draft
):
    _, version = seed_instrument_draft
    questions = [_question(version.id, "Q1"), _question(version.id, "Q2")]
    session.add_all(questions)
    await session.flush()
    survey = Survey(
        project_id=seed_project.id,
        created_by_user_id=seed_user.id,
        instrument_version_id=version.id,
        name="Synthetic partial custom survey",
        survey_type="ACADEMIC",
    )
    session.add(survey)
    await session.flush()
    session.add(SurveyQuestion(survey_id=survey.id, question_id=questions[0].id, sort_order=0))
    study = Study(
        project_id=seed_project.id,
        survey_id=survey.id,
        instrument_version_id=version.id,
        name="Synthetic academic study",
        study_type="ACADEMIC",
        status="DRAFT",
        min_publishable_n=5,
    )
    session.add(study)
    await session.commit()

    opened = await StudyService(session).open(study.id)

    assert opened.status == "OPEN"
    snapshot = await session.scalar(
        select(StudySnapshot).where(StudySnapshot.study_id == study.id)
    )
    assert len(snapshot.snapshot_data["survey"]["questions"]) == 1
