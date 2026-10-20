from sqlalchemy import func, select

from app.models.analysis import AnalysisRun
from app.models.study import Study
from app.services.response_descriptive_service import ResponseDescriptiveService


def test_measurement_level_inference_and_visual_group_precedence() -> None:
    assert ResponseDescriptiveService.infer_measurement_level("LIKERT", None) == "ORDINAL"
    assert ResponseDescriptiveService.infer_measurement_level("SINGLE_CHOICE", None) == "NOMINAL"
    assert ResponseDescriptiveService.infer_measurement_level("LIKERT", "NOMINAL") == "NOMINAL"

    topic = ResponseDescriptiveService.visual_group(None, "  Carga laboral ", "Perfil")
    assert (topic.group_type, topic.label) == ("TOPIC", "Carga laboral")
    category = ResponseDescriptiveService.visual_group(None, None, "Perfil")
    assert (category.group_type, category.label) == ("CATEGORY", "Perfil")
    ungrouped = ResponseDescriptiveService.visual_group(None, None, None)
    assert (ungrouped.group_type, ungrouped.label) == ("UNGROUPED", "Sin agrupación")


async def test_response_descriptives_groups_frequencies_and_valid_sessions(
    client, session, seed_user, seed_project, seed_instrument_draft
) -> None:
    _instrument, version = seed_instrument_draft
    option_set = {
        "name": "Frecuencia",
        "options": [
            {"raw_code": "N", "label": "Nunca", "numeric_value": 1, "sort_order": 10},
            {"raw_code": "A", "label": "A veces", "numeric_value": 2, "sort_order": 20},
            {"raw_code": "S", "label": "Siempre", "numeric_value": 3, "sort_order": 30},
        ],
    }
    items = []
    payloads = [
        {
            "code": "P_DIM",
            "question_text": "Pregunta en dimensión",
            "question_type": "LIKERT",
            "short_label": "Tema ignorado por dimensión",
            "option_set": option_set,
        },
        {
            "code": "P_TOPIC",
            "question_text": "Pregunta temática",
            "question_type": "LIKERT",
            "short_label": "Carga laboral",
            "option_set": option_set,
        },
        {
            "code": "P_PROFILE",
            "question_text": "Sexo",
            "question_type": "SINGLE_CHOICE",
            "category": "Perfil",
            "option_set": {
                "name": "Sexo",
                "options": [
                    {"raw_code": "F", "label": "Femenino", "sort_order": 1},
                    {"raw_code": "M", "label": "Masculino", "sort_order": 2},
                ],
            },
        },
        {
            "code": "P_FREE",
            "question_text": "Horas semanales",
            "question_type": "NUMBER",
        },
    ]
    for payload in payloads:
        response = await client.post(
            f"/api/v1/instrument-versions/{version.id}/items", json=payload
        )
        assert response.status_code == 201, response.text
        items.append(response.json())

    root = (
        await client.post(
            f"/api/v1/instrument-versions/{version.id}/structure-variables",
            json={"code": "ROOT", "name": "Puntaje raíz", "role": "OUTCOME"},
        )
    ).json()
    dimension = (
        await client.post(
            f"/api/v1/instrument-versions/{version.id}/constructs",
            json={
                "parent_id": root["id"],
                "code": "DIM",
                "name": "Dimensión formal",
                "construct_type": "DIMENSION",
            },
        )
    ).json()
    assigned = await client.post(
        f"/api/v1/constructs/{dimension['id']}/items",
        json={"question_id": items[0]["id"], "weight": 1},
    )
    assert assigned.status_code == 201, assigned.text

    variable = await client.post(
        f"/api/v1/projects/{seed_project.id}/variables",
        json={
            "instrument_version_id": version.id,
            "question_id": items[2]["id"],
            "code": "sexo",
            "name": "Sexo",
            "variable_type": "EXOGENOUS",
            "data_type": "CATEGORY",
            "measurement_level": "NOMINAL",
            "role": "EXOGENOUS",
        },
    )
    assert variable.status_code == 201, variable.text

    survey = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/surveys/from-instrument",
            json={
                "created_by_user_id": seed_user.id,
                "instrument_version_id": version.id,
                "name": "Encuesta descriptiva",
            },
        )
    ).json()
    study = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/studies",
            json={
                "survey_id": survey["id"],
                "name": "Aplicación descriptiva",
                "study_type": "CUSTOM",
                "settings": {
                    "response_validation": {
                        "min_answered_count": 3,
                        "min_completion_percent": 70,
                    }
                },
            },
        )
    ).json()
    await client.post(f"/api/v1/studies/{study['id']}/open")

    valid = (
        await client.post(f"/api/v1/public/studies/{study['public_id']}/response-sessions")
    ).json()
    answers = [
        {"raw_code": "A"},
        {"raw_code": "S"},
        {"raw_code": "F"},
        {"numeric_value": 40},
    ]
    for item, answer in zip(items, answers, strict=True):
        response = await client.put(
            f"/api/v1/response-sessions/{valid['id']}/responses/{item['id']}",
            json=answer,
        )
        assert response.status_code == 200, response.text
    completed = await client.post(f"/api/v1/response-sessions/{valid['id']}/complete")
    assert completed.json()["validation_status"] == "VALID"

    valid_with_missing = (
        await client.post(f"/api/v1/public/studies/{study['public_id']}/response-sessions")
    ).json()
    for item, answer in zip(items[:3], answers[:3], strict=True):
        response = await client.put(
            f"/api/v1/response-sessions/{valid_with_missing['id']}/responses/{item['id']}",
            json=answer,
        )
        assert response.status_code == 200, response.text
    completed_with_missing = await client.post(
        f"/api/v1/response-sessions/{valid_with_missing['id']}/complete"
    )
    assert completed_with_missing.json()["validation_status"] == "VALID"

    incomplete = (
        await client.post(f"/api/v1/public/studies/{study['public_id']}/response-sessions")
    ).json()
    await client.put(
        f"/api/v1/response-sessions/{incomplete['id']}/responses/{items[0]['id']}",
        json={"raw_code": "N"},
    )

    before_runs = await session.scalar(select(func.count()).select_from(AnalysisRun))
    private_response = await client.get(f"/api/v1/studies/{study['id']}/response-descriptives")
    assert private_response.status_code == 200
    assert all(not question["frequencies"] for question in private_response.json()["questions"])
    study_model = await session.get(Study, study["id"])
    study_model.min_publishable_n = 1
    await session.commit()
    response = await client.get(f"/api/v1/studies/{study['id']}/response-descriptives")
    assert response.status_code == 200, response.text
    body = response.json()
    after_runs = await session.scalar(select(func.count()).select_from(AnalysisRun))

    assert before_runs == after_runs == 0
    assert body["summary"] == {
        "included_cases": 2,
        "question_count": 4,
        "answered_cells": 7,
        "missing_cells": 1,
        "missing_pct": 12.5,
    }
    assert [group["group_type"] for group in body["groups"]] == [
        "DIMENSION",
        "TOPIC",
        "CATEGORY",
        "UNGROUPED",
    ]
    by_code = {question["code"]: question for question in body["questions"]}
    ordinal = by_code["P_DIM"]
    assert ordinal["group_label"] == "Dimensión formal"
    assert ordinal["measurement_level"] == "ORDINAL"
    assert [row["code"] for row in ordinal["frequencies"]] == ["N", "A", "S"]
    assert [row["n"] for row in ordinal["frequencies"]] == [0, 2, 0]
    assert [row["cumulative_percentage"] for row in ordinal["frequencies"]] == [
        0.0,
        100.0,
        100.0,
    ]
    assert by_code["P_TOPIC"]["group_label"] == "Carga laboral"
    assert by_code["P_PROFILE"]["group_label"] == "Perfil"
    assert by_code["P_PROFILE"]["variable_code"] == "sexo"
    assert by_code["P_FREE"]["group_label"] == "Sin agrupación"
    assert by_code["P_FREE"]["missing_n"] == 1
    assert by_code["P_FREE"]["numeric"]["mean"] == 40.0
