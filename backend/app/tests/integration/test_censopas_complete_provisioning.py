"""El enlace empresarial debe contener el instrumento, no solo el perfil."""

import pytest
from sqlalchemy import select
from types import SimpleNamespace
from datetime import UTC, datetime
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.instrument import Instrument, InstrumentVersion
from app.models.question import Question
from app.models.survey import SurveyQuestion
from app.models.survey import Survey
from app.models.study import Study
from app.models.response import ResponseSession
from app.services import auto_scoring_service
from app.services.censopas_provisioning_service import CensopasProvisioningService


@pytest.mark.asyncio
async def test_official_survey_links_profile_and_scored_items(session, seed_project, monkeypatch):
    instrument = Instrument(
        code="CENSOPAS_COPSOQ", name="CENSOPAS-COPSOQ", is_system=True, status="LOCKED"
    )
    session.add(instrument)
    await session.flush()
    version = InstrumentVersion(
        instrument_id=instrument.id, version_code="SHORT-OFICIAL", status="LOCKED",
        config={"censopas_version_kind": "SHORT", "censopas_expected": {"questions": 3, "scored": 2}},
    )
    session.add(version)
    await session.flush()
    questions = [
        Question(instrument_version_id=version.id, code="C-001", question_text="Perfil",
                 question_type="TEXT", research_role="EXOGENOUS", is_scored=False,
                 is_required_default=True, sort_order=1),
        Question(instrument_version_id=version.id, code="P-001", question_text="Ítem 1",
                 question_type="LIKERT", research_role="ENDOGENOUS", is_scored=True,
                 is_required_default=True, sort_order=2),
        Question(instrument_version_id=version.id, code="P-002", question_text="Ítem 2",
                 question_type="LIKERT", research_role="ENDOGENOUS", is_scored=True,
                 is_required_default=True, sort_order=3),
    ]
    session.add_all(questions)
    await session.flush()

    async def barem_stub(*_args):
        return SimpleNamespace(id=1)

    monkeypatch.setattr(CensopasProvisioningService, "_ensure_reference_barem", barem_stub)
    seed_project.metadata_ = {"requested_version_kind": "SHORT"}
    await CensopasProvisioningService(session).provision_project(seed_project)
    survey_id = seed_project.metadata_["survey_id"]
    links = list((await session.execute(
        select(SurveyQuestion).where(SurveyQuestion.survey_id == survey_id)
        .order_by(SurveyQuestion.sort_order)
    )).scalars())
    assert [link.question_id for link in links] == [question.id for question in questions]
    assert links[0].section_id != links[1].section_id
    assert links[1].section_id == links[2].section_id


@pytest.mark.asyncio
async def test_auto_scoring_starts_only_after_publishable_sample(
    session, engine, seed_project, monkeypatch,
):
    instrument = Instrument(
        code="CENSOPAS_COPSOQ", name="CENSOPAS-COPSOQ", is_system=True,
    )
    session.add(instrument)
    await session.flush()
    version = InstrumentVersion(
        instrument_id=instrument.id, version_code="SHORT-OFICIAL", status="LOCKED",
    )
    session.add(version)
    await session.flush()
    survey = Survey(
        project_id=seed_project.id, created_by_user_id=seed_project.owner_user_id,
        instrument_version_id=version.id, name="Prueba automática", survey_type="CENSO",
    )
    session.add(survey)
    await session.flush()
    study = Study(
        project_id=seed_project.id, survey_id=survey.id,
        instrument_version_id=version.id, name="Estudio", study_type="CENSO",
        status="OPEN", min_publishable_n=2,
    )
    session.add(study)
    await session.flush()
    session.add(ResponseSession(
        study_id=study.id, status="COMPLETED", validation_status="VALID",
        completed_at=datetime.now(UTC),
    ))
    await session.commit()

    calls = []

    async def fake_scoring(_session, study_id):
        calls.append(study_id)
        return SimpleNamespace(status="COMPLETED"), None

    monkeypatch.setattr(auto_scoring_service, "engine", engine)
    monkeypatch.setattr(auto_scoring_service, "AsyncSessionLocal",
                        async_sessionmaker(engine, expire_on_commit=False))
    monkeypatch.setattr(auto_scoring_service, "run_canonical_scoring", fake_scoring)

    await auto_scoring_service.refresh_scores_for_study(study.id)
    assert calls == []
    session.add(ResponseSession(
        study_id=study.id, status="COMPLETED", validation_status="VALID",
        completed_at=datetime.now(UTC),
    ))
    await session.commit()
    await auto_scoring_service.refresh_scores_for_study(study.id)
    assert calls == [study.id]
