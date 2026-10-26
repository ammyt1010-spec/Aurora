"""CENSOPAS project creation must attach the entire selected version."""

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.analytics_plan import AnalyticsPlan
from app.models.construct import Construct, ConstructItem
from app.models.instrument import Instrument, InstrumentVersion
from app.models.question import Question
from app.models.survey import Survey, SurveyQuestion, SurveySection


@pytest.mark.parametrize(
    ("kind", "total", "scored", "contextual"),
    [("SHORT", 42, 31, 11), ("MEDIUM", 112, 69, 43)],
)
async def test_project_create_endpoint_provisions_every_version_item_in_order(
    client, session, seed_user, seed_project, kind, total, scored, contextual
):
    instrument = Instrument(
        code="CENSOPAS_COPSOQ",
        name="CENSOPAS-COPSOQ synthetic test catalog",
        is_system=True,
        status="ACTIVE",
    )
    session.add(instrument)
    await session.flush()
    version = InstrumentVersion(
        instrument_id=instrument.id,
        version_code=f"{kind}-OFICIAL",
        version_name=f"Synthetic {kind}",
        status="ACTIVE",
        config={"censopas_version_kind": kind},
    )
    session.add(version)
    await session.flush()

    questions = []
    for index in range(total):
        is_scored = index < scored
        questions.append(
            Question(
                instrument_version_id=version.id,
                code=f"{kind}-Q{index + 1:03}",
                question_text=f"Synthetic item {index + 1}",
                question_type="LIKERT",
                research_role="ENDOGENOUS" if is_scored else "EXOGENOUS",
                category="DIMENSION" if is_scored else "CONTEXT",
                is_scored=is_scored,
                is_required_default=True,
                sort_order=index + 1,
            )
        )
    session.add_all(questions)
    await session.flush()

    # A scored construct is needed by the reference-barem provisioner. SHORT
    # links scored items directly to its dimensions; MEDIUM links through
    # subdimensions, matching the catalog's two shapes.
    dimension = Construct(
        instrument_version_id=version.id,
        code=f"{kind}-D1",
        name="Synthetic dimension",
        construct_type="DIMENSION",
        sort_order=1,
    )
    session.add(dimension)
    await session.flush()
    scored_construct = dimension
    if kind == "MEDIUM":
        scored_construct = Construct(
            instrument_version_id=version.id,
            parent_id=dimension.id,
            code=f"{kind}-S1",
            name="Synthetic subdimension",
            construct_type="SUBDIMENSION",
            sort_order=1,
        )
        session.add(scored_construct)
        await session.flush()
    session.add_all(
        [
            ConstructItem(
                construct_id=scored_construct.id,
                question_id=question.id,
                weight=1,
                item_role="SCORED",
                sort_order=index,
            )
            for index, question in enumerate(questions[:scored], start=1)
        ]
    )
    session.add(AnalyticsPlan(code="STANDARD", name="Standard", level=1, is_active=True))
    await session.commit()

    client.headers["Authorization"] = f"Bearer {create_access_token(seed_user.id)}"
    response = await client.post(
        "/api/v1/projects",
        json={
            "owner_user_id": seed_user.id,
            "organization_id": seed_project.organization_id,
            "name": f"QA synthetic CENSOPAS {kind}",
            "project_type": "CENSO",
            "censopas_study": {
                "instrument_version": kind,
                "analytics_plan": "STANDARD",
            },
        },
    )
    assert response.status_code == 201, response.text
    project_data = response.json()
    survey_id = project_data["metadata"]["survey_id"]

    survey = await session.get(Survey, survey_id)
    assert survey is not None
    links = list(
        (
            await session.execute(
                select(SurveyQuestion)
                .where(SurveyQuestion.survey_id == survey_id)
                .order_by(SurveyQuestion.sort_order)
            )
        )
        .scalars()
        .all()
    )
    assert [link.question_id for link in links] == [question.id for question in questions]
    assert len(links) == total
    assert sum(question.is_scored for question in questions) == scored
    assert sum(not question.is_scored for question in questions) == contextual

    sections = {
        section.id: section.section_kind
        for section in (
            await session.execute(
                select(SurveySection).where(SurveySection.survey_id == survey_id)
            )
        ).scalars()
    }
    assert [sections[link.section_id] for link in links] == [
        "INSTRUMENT" if question.is_scored else "EXOGENOUS"
        for question in questions
    ]
