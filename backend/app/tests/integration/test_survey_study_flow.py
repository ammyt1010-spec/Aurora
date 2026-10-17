"""Flujo Fase 3 (surveys/studies/responses) + Fase 4 (dataset).

crear survey desde instrumento -> crear estudio -> abrir -> crear sesión de
respuesta -> responder -> completar -> data-dictionary -> long/wide dataset.
"""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


@pytest.fixture(autouse=True)
def _auth_survey_client(client: AsyncClient, seed_user):
    token = create_access_token(seed_user.id)
    client.headers["Authorization"] = f"Bearer {token}"


async def test_full_survey_study_response_flow(
    client: AsyncClient, session, seed_user, seed_project, seed_instrument_draft
) -> None:
    instrument, version = seed_instrument_draft
    project = seed_project

    item1 = (
        await client.post(
            f"/api/v1/instrument-versions/{version.id}/items",
            json={"code": "P1", "question_text": "Pregunta 1", "question_type": "NUMBER"},
        )
    ).json()
    item2 = (
        await client.post(
            f"/api/v1/instrument-versions/{version.id}/items",
            json={"code": "P2", "question_text": "Pregunta 2", "question_type": "TEXT"},
        )
    ).json()

    survey_resp = await client.post(
        f"/api/v1/projects/{project.id}/surveys/from-instrument",
        json={
            "created_by_user_id": seed_user.id,
            "instrument_version_id": version.id,
            "name": "Encuesta académica",
        },
    )
    assert survey_resp.status_code == 201, survey_resp.text
    survey = survey_resp.json()
    assert survey["instrument_version_id"] == version.id

    variable_resp = await client.post(
        f"/api/v1/projects/{project.id}/variables",
        json={
            "code": "p1_var",
            "name": "Pregunta 1",
            "variable_type": "QUESTION",
            "data_type": "INTEGER",
            "measurement_level": "SCALE",
            "question_id": item1["id"],
        },
    )
    assert variable_resp.status_code == 201, variable_resp.text

    study_resp = await client.post(
        f"/api/v1/projects/{project.id}/studies",
        json={"survey_id": survey["id"], "name": "Aplicación 2026-I", "study_type": "ACADEMIC"},
    )
    assert study_resp.status_code == 201, study_resp.text
    study = study_resp.json()
    assert study["status"] == "DRAFT"
    assert study["instrument_version_id"] == version.id

    unit_type_resp = await client.post(
        f"/api/v1/studies/{study['id']}/unit-types",
        json={"code": "CENTRO", "name": "Centro laboral"},
    )
    assert unit_type_resp.status_code == 201, unit_type_resp.text
    unit_type = unit_type_resp.json()
    unit_resp = await client.post(
        f"/api/v1/study-unit-types/{unit_type['id']}/units",
        json={"code": "LIMA", "name": "Centro Lima"},
    )
    assert unit_resp.status_code == 201, unit_resp.text
    unit = unit_resp.json()

    # No se puede crear sesión de respuesta con el estudio en DRAFT.
    blocked_resp = await client.post(f"/api/v1/studies/{study['id']}/response-sessions")
    assert blocked_resp.status_code == 409

    open_resp = await client.post(f"/api/v1/studies/{study['id']}/open")
    assert open_resp.status_code == 200, open_resp.text
    assert open_resp.json()["status"] == "OPEN"

    session_resp = await client.post(f"/api/v1/studies/{study['id']}/response-sessions")
    assert session_resp.status_code == 201, session_resp.text
    response_session = session_resp.json()
    assert response_session["status"] == "STARTED"

    units_resp = await client.put(
        f"/api/v1/response-sessions/{response_session['id']}/units",
        json={"unit_ids": [unit["id"]]},
    )
    assert units_resp.status_code == 200, units_resp.text
    assert units_resp.json()["unit_ids"] == [unit["id"]]

    put1 = await client.put(
        f"/api/v1/response-sessions/{response_session['id']}/responses/{item1['id']}",
        json={"numeric_value": 27},
    )
    assert put1.status_code == 200, put1.text

    put2 = await client.put(
        f"/api/v1/response-sessions/{response_session['id']}/responses/{item2['id']}",
        json={"text_value": "respuesta libre"},
    )
    assert put2.status_code == 200, put2.text

    complete_resp = await client.post(
        f"/api/v1/response-sessions/{response_session['id']}/complete"
    )
    assert complete_resp.status_code == 200, complete_resp.text
    completed = complete_resp.json()
    assert completed["status"] == "COMPLETED"
    assert completed["completion_pct"] == 100.0
    assert completed["validation_status"] == "VALID"

    frozen_units_resp = await client.put(
        f"/api/v1/response-sessions/{response_session['id']}/units",
        json={"unit_ids": []},
    )
    assert frozen_units_resp.status_code == 409

    dictionary_resp = await client.get(f"/api/v1/studies/{study['id']}/data-dictionary")
    assert dictionary_resp.status_code == 200
    dictionary = dictionary_resp.json()
    codes = {entry["variable_code"] for entry in dictionary["entries"]}
    assert "p1_var" in codes

    long_resp = await client.get(f"/api/v1/studies/{study['id']}/dataset/long")
    assert long_resp.status_code == 200
    long_rows = long_resp.json()["rows"]
    assert len(long_rows) == 2
    assert any(row["variable_code"] == "p1_var" and row["numeric_value"] == 27 for row in long_rows)

    wide_resp = await client.get(f"/api/v1/studies/{study['id']}/dataset/wide")
    assert wide_resp.status_code == 200
    wide = wide_resp.json()
    assert len(wide["rows"]) == 1
    assert wide["rows"][0]["p1_var"] == 27

    del instrument


async def test_study_lifecycle_transitions(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    _instrument, version = seed_instrument_draft
    project = seed_project

    await client.post(
        f"/api/v1/instrument-versions/{version.id}/items",
        json={"code": "P1", "question_text": "Pregunta 1", "question_type": "TEXT"},
    )
    survey = (
        await client.post(
            f"/api/v1/projects/{project.id}/surveys/from-instrument",
            json={
                "created_by_user_id": seed_user.id,
                "instrument_version_id": version.id,
                "name": "Encuesta",
            },
        )
    ).json()
    study = (
        await client.post(
            f"/api/v1/projects/{project.id}/studies",
            json={"survey_id": survey["id"], "name": "Estudio", "study_type": "ACADEMIC"},
        )
    ).json()

    # No se puede cerrar sin abrir primero.
    invalid_close = await client.post(f"/api/v1/studies/{study['id']}/close")
    assert invalid_close.status_code == 409

    await client.post(f"/api/v1/studies/{study['id']}/open")
    close_resp = await client.post(f"/api/v1/studies/{study['id']}/close")
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "CLOSED"

    archive_resp = await client.post(f"/api/v1/studies/{study['id']}/archive")
    assert archive_resp.status_code == 200
    assert archive_resp.json()["status"] == "ARCHIVED"


async def test_open_study_locks_active_instrument_version(
    client: AsyncClient, session, seed_user, seed_project
) -> None:
    from app.models.instrument import Instrument, InstrumentVersion
    from app.models.question import Question

    project = seed_project

    instrument = Instrument(name="Instrumento activo", is_system=False, status="ACTIVE")
    session.add(instrument)
    await session.flush()
    version = InstrumentVersion(
        instrument_id=instrument.id, version_code="V1", status="ACTIVE"
    )
    session.add(version)
    await session.flush()
    question = Question(
        instrument_version_id=version.id, question_text="P1", question_type="TEXT", code="P1"
    )
    session.add(question)
    await session.commit()
    await session.refresh(version)
    variable = (
        await client.post(
            f"/api/v1/instrument-versions/{version.id}/structure-variables",
            json={"code": "VAR", "name": "Variable"},
        )
    ).json()

    survey = (
        await client.post(
            f"/api/v1/projects/{project.id}/surveys/from-instrument",
            json={
                "created_by_user_id": seed_user.id,
                "instrument_version_id": version.id,
                "name": "Encuesta ACTIVE",
            },
        )
    ).json()

    # Antes de abrir el estudio, la versión ACTIVE sigue editable (cambios controlados).
    pre_open_resp = await client.post(
        f"/api/v1/instrument-versions/{version.id}/constructs",
        json={"parent_id": variable["id"], "code": "D1", "name": "D1", "construct_type": "DIMENSION"},
    )
    assert pre_open_resp.status_code == 201

    study = (
        await client.post(
            f"/api/v1/projects/{project.id}/studies",
            json={"survey_id": survey["id"], "name": "Estudio activo", "study_type": "ACADEMIC"},
        )
    ).json()
    await client.post(f"/api/v1/studies/{study['id']}/open")

    locked_resp = await client.post(
        f"/api/v1/instrument-versions/{version.id}/constructs",
        json={"parent_id": variable["id"], "code": "D2", "name": "D2", "construct_type": "DIMENSION"},
    )
    assert locked_resp.status_code == 409
    assert locked_resp.json()["reason"] == "STUDY_OPEN_STRUCTURAL_LOCK"


async def test_open_study_locks_draft_instrument_version(
    client: AsyncClient, session, seed_user, seed_project
) -> None:
    """E-06: antes sólo se bloqueaba con la versión ACTIVE; una versión
    DRAFT referenciada por un estudio OPEN también debe congelarse."""
    from app.models.instrument import Instrument, InstrumentVersion
    from app.models.question import Question

    project = seed_project

    instrument = Instrument(name="Instrumento borrador", is_system=False, status="DRAFT")
    session.add(instrument)
    await session.flush()
    version = InstrumentVersion(instrument_id=instrument.id, version_code="V1", status="DRAFT")
    session.add(version)
    await session.flush()
    question = Question(
        instrument_version_id=version.id, question_text="P1", question_type="TEXT", code="P1"
    )
    session.add(question)
    await session.commit()
    await session.refresh(version)
    variable = (
        await client.post(
            f"/api/v1/instrument-versions/{version.id}/structure-variables",
            json={"code": "VAR", "name": "Variable"},
        )
    ).json()

    survey = (
        await client.post(
            f"/api/v1/projects/{project.id}/surveys/from-instrument",
            json={
                "created_by_user_id": seed_user.id,
                "instrument_version_id": version.id,
                "name": "Encuesta DRAFT",
            },
        )
    ).json()

    # Antes de abrir el estudio, la versión DRAFT es editable.
    pre_open_resp = await client.post(
        f"/api/v1/instrument-versions/{version.id}/constructs",
        json={"parent_id": variable["id"], "code": "D1", "name": "D1", "construct_type": "DIMENSION"},
    )
    assert pre_open_resp.status_code == 201

    study = (
        await client.post(
            f"/api/v1/projects/{project.id}/studies",
            json={"survey_id": survey["id"], "name": "Estudio borrador", "study_type": "ACADEMIC"},
        )
    ).json()
    await client.post(f"/api/v1/studies/{study['id']}/open")

    locked_resp = await client.post(
        f"/api/v1/instrument-versions/{version.id}/constructs",
        json={"parent_id": variable["id"], "code": "D2", "name": "D2", "construct_type": "DIMENSION"},
    )
    assert locked_resp.status_code == 409
    assert locked_resp.json()["reason"] == "STUDY_OPEN_STRUCTURAL_LOCK"

    # La vía de escape (clonar una nueva versión editable) sigue disponible.
    clone_resp = await client.post(
        f"/api/v1/instruments/{instrument.id}/versions/{version.id}/clone",
        json={"version_code": "V2", "version_name": "Versión editable"},
    )
    assert clone_resp.status_code == 201, clone_resp.text
    assert clone_resp.json()["status"] == "DRAFT"
