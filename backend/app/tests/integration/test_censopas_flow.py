"""Flujo Fase 6 (CENSOPAS): scoring_rules -> barem -> scoring -> resultados con
privacidad (harness §27-31)."""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


@pytest.fixture(autouse=True)
def _auth_censopas_client(client: AsyncClient, seed_user):
    token = create_access_token(seed_user.id)
    client.headers["Authorization"] = f"Bearer {token}"



async def _setup_censopas_study(
    client: AsyncClient,
    seed_user,
    seed_project,
    min_publishable_n: int,
    *,
    create_scoring_rules: bool = True,
    create_sessions: bool = True,
    with_units: bool = False,
    unit_specs: list[dict] | None = None,
):
    instrument = (
        await client.post(
            "/api/v1/instruments", json={"name": "CENSOPAS test", "is_system": False}
        )
    ).json()
    version = (
        await client.post(
            f"/api/v1/instruments/{instrument['id']}/versions",
            json={"version_code": "V1", "status": "DRAFT"},
        )
    ).json()

    variable = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/structure-variables",
            json={"code": "CENSOPAS", "name": "CENSOPAS", "role": "OUTCOME"},
        )
    ).json()

    item1 = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/items",
            json={"code": "P1", "question_text": "Exigencia 1", "question_type": "LIKERT"},
        )
    ).json()
    item2 = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/items",
            json={"code": "P2", "question_text": "Exigencia 2", "question_type": "LIKERT"},
        )
    ).json()

    dimension = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/constructs",
            json={"parent_id": variable["id"], "code": "D1", "name": "Exigencias psicológicas", "construct_type": "DIMENSION"},
        )
    ).json()
    await client.post(
        f"/api/v1/constructs/{dimension['id']}/items",
        json={"question_id": item1["id"], "weight": 1, "scoring_direction": "DIRECT"},
    )
    await client.post(
        f"/api/v1/constructs/{dimension['id']}/items",
        json={"question_id": item2["id"], "weight": 1, "scoring_direction": "REVERSE"},
    )

    scale_map = {"1": 0, "2": 25, "3": 50, "4": 75, "5": 100}
    if create_scoring_rules:
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/scoring-rules",
            json={"question_id": item1["id"], "parameters": {"map": scale_map}},
        )
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/scoring-rules",
            json={"question_id": item2["id"], "parameters": {"map": scale_map}},
        )

    barem = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/barems",
            json={"name": "Barem de prueba"},
        )
    ).json()
    await client.post(
        f"/api/v1/barems/{barem['id']}/cutoffs",
        json={
            "construct_id": dimension["id"],
            "cut_1": 33,
            "cut_2": 66,
            "direction": "LOWER_BETTER",
        },
    )

    survey = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/surveys/from-instrument",
            json={
                "created_by_user_id": seed_user.id,
                "instrument_version_id": version["id"],
                "name": "Encuesta CENSOPAS",
            },
        )
    ).json()
    study = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/studies",
            json={
                "survey_id": survey["id"],
                "name": "Estudio CENSOPAS",
                "study_type": "CENSO",
                "min_publishable_n": min_publishable_n,
            },
        )
    ).json()
    await client.patch(f"/api/v1/studies/{study['id']}", json={"barem_id": barem["id"]})
    units = []
    if with_units or unit_specs:
        unit_type = (
            await client.post(
                f"/api/v1/studies/{study['id']}/unit-types",
                json={"code": "CENTRO", "name": "Centro laboral"},
            )
        ).json()
        units_by_code: dict[str, dict] = {}
        specs = unit_specs or [
            {"code": "A", "name": "Centro A"},
            {"code": "B", "name": "Centro B"},
        ]
        for spec in specs:
            payload = {"code": spec["code"], "name": spec["name"]}
            if spec.get("parent_code"):
                payload["parent_id"] = units_by_code[spec["parent_code"]]["id"]
            unit = (
                await client.post(
                    f"/api/v1/study-unit-types/{unit_type['id']}/units", json=payload
                )
            ).json()
            units.append(unit)
            units_by_code[spec["code"]] = unit
        study["_test_unit_type_id"] = unit_type["id"]
        study["_test_units_by_code"] = units_by_code
    await client.post(f"/api/v1/studies/{study['id']}/open")

    # 3 respondentes: dos con exigencia alta (riesgo), uno bajo.
    if create_sessions:
        for session_index, (p1_code, p2_code) in enumerate([("5", "1"), ("5", "1"), ("1", "5")]):
            rs = (await client.post(f"/api/v1/studies/{study['id']}/response-sessions")).json()
            if units:
                unit = units[0] if session_index == 0 else units[1]
                await client.put(
                    f"/api/v1/response-sessions/{rs['id']}/units",
                    json={"unit_ids": [unit["id"]]},
                )
            await client.put(
                f"/api/v1/response-sessions/{rs['id']}/responses/{item1['id']}",
                json={"raw_code": p1_code},
            )
            await client.put(
                f"/api/v1/response-sessions/{rs['id']}/responses/{item2['id']}",
                json={"raw_code": p2_code},
            )
            await client.post(f"/api/v1/response-sessions/{rs['id']}/complete")

    return study, dimension


async def test_censopas_media_dimension_gets_bands_from_subdimension_items(
    client: AsyncClient, seed_user, seed_project
) -> None:
    """Versión MEDIA: D1 no tiene item_links directos (sólo S1/S2 los tienen),
    pero debe quedar puntuada y baremada igual — antes de la corrección, D1
    quedaba con bands=[] (bug bloqueante, ver auditoría de Resultados)."""
    instrument = (
        await client.post("/api/v1/instruments", json={"name": "CENSOPAS test", "is_system": False})
    ).json()
    version = (
        await client.post(
            f"/api/v1/instruments/{instrument['id']}/versions",
            json={"version_code": "V1", "status": "DRAFT"},
        )
    ).json()
    variable = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/structure-variables",
            json={"code": "CENSOPAS", "name": "CENSOPAS", "role": "OUTCOME"},
        )
    ).json()
    item1 = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/items",
            json={"code": "P1", "question_text": "Exigencia 1", "question_type": "LIKERT"},
        )
    ).json()
    item2 = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/items",
            json={"code": "P2", "question_text": "Exigencia 2", "question_type": "LIKERT"},
        )
    ).json()

    dimension = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/constructs",
            json={"parent_id": variable["id"], "code": "D1", "name": "Exigencias psicológicas", "construct_type": "DIMENSION"},
        )
    ).json()
    sub1 = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/constructs",
            json={"parent_id": dimension["id"], "code": "S1", "name": "Subdimensión 1", "construct_type": "SUBDIMENSION"},
        )
    ).json()
    sub2 = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/constructs",
            json={"parent_id": dimension["id"], "code": "S2", "name": "Subdimensión 2", "construct_type": "SUBDIMENSION"},
        )
    ).json()
    # Sólo las subdimensiones tienen item_links directos — D1 (la dimensión)
    # no tiene ninguno, tal como en la versión MEDIA real.
    await client.post(
        f"/api/v1/constructs/{sub1['id']}/items",
        json={"question_id": item1["id"], "weight": 1, "scoring_direction": "DIRECT"},
    )
    await client.post(
        f"/api/v1/constructs/{sub2['id']}/items",
        json={"question_id": item2["id"], "weight": 1, "scoring_direction": "REVERSE"},
    )

    scale_map = {"1": 0, "2": 25, "3": 50, "4": 75, "5": 100}
    await client.post(
        f"/api/v1/instrument-versions/{version['id']}/scoring-rules",
        json={"question_id": item1["id"], "parameters": {"map": scale_map}},
    )
    await client.post(
        f"/api/v1/instrument-versions/{version['id']}/scoring-rules",
        json={"question_id": item2["id"], "parameters": {"map": scale_map}},
    )

    barem = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/barems",
            json={"name": "Barem de prueba MEDIA"},
        )
    ).json()
    # Cortes tanto para D1 (dimensión) como para S1 (subdimensión) — ambos
    # niveles deben quedar baremados en la versión MEDIA.
    for construct_id in (dimension["id"], sub1["id"]):
        await client.post(
            f"/api/v1/barems/{barem['id']}/cutoffs",
            json={"construct_id": construct_id, "cut_1": 33, "cut_2": 66, "direction": "LOWER_BETTER"},
        )

    survey = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/surveys/from-instrument",
            json={
                "created_by_user_id": seed_user.id,
                "instrument_version_id": version["id"],
                "name": "Encuesta CENSOPAS media",
            },
        )
    ).json()
    study = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/studies",
            json={
                "survey_id": survey["id"],
                "name": "Estudio CENSOPAS media",
                "study_type": "CENSO",
                "min_publishable_n": 1,
            },
        )
    ).json()
    await client.patch(f"/api/v1/studies/{study['id']}", json={"barem_id": barem["id"]})
    await client.post(f"/api/v1/studies/{study['id']}/open")

    for p1_code, p2_code in (("5", "1"), ("5", "1"), ("1", "5")):
        rs = (await client.post(f"/api/v1/studies/{study['id']}/response-sessions")).json()
        await client.put(
            f"/api/v1/response-sessions/{rs['id']}/responses/{item1['id']}",
            json={"raw_code": p1_code},
        )
        await client.put(
            f"/api/v1/response-sessions/{rs['id']}/responses/{item2['id']}",
            json={"raw_code": p2_code},
        )
        await client.post(f"/api/v1/response-sessions/{rs['id']}/complete")

    scoring_resp = await client.post(f"/api/v1/studies/{study['id']}/scoring")
    assert scoring_resp.status_code == 200, scoring_resp.text

    results_resp = await client.get(f"/api/v1/studies/{study['id']}/censopas/results")
    assert results_resp.status_code == 200, results_resp.text
    results = results_resp.json()["results"]

    d1_result = next(r for r in results if r["construct_id"] == dimension["id"])
    assert d1_result["n_valid"] == 3
    assert d1_result["favorable_n"] + d1_result["intermediate_n"] + d1_result["unfavorable_n"] == 3
    assert d1_result["collective_classification"] is not None
    assert d1_result["construct_type"] == "DIMENSION"

    s1_result = next(r for r in results if r["construct_id"] == sub1["id"])
    assert s1_result["n_valid"] == 3
    assert s1_result["favorable_n"] + s1_result["intermediate_n"] + s1_result["unfavorable_n"] == 3
    assert s1_result["construct_type"] == "SUBDIMENSION"


async def test_censopas_scoring_and_results_with_low_min_n(
    client: AsyncClient, seed_user, seed_project
) -> None:
    study, dimension = await _setup_censopas_study(client, seed_user, seed_project, min_publishable_n=1)

    scoring_resp = await client.post(f"/api/v1/studies/{study['id']}/censopas/scoring")
    assert scoring_resp.status_code == 200, scoring_resp.text
    assert scoring_resp.json()["status"] == "COMPLETED"

    results_resp = await client.get(f"/api/v1/studies/{study['id']}/censopas/results")
    assert results_resp.status_code == 200, results_resp.text
    body = results_resp.json()
    assert body["scoring_status"] == "NOT_CONFIGURED"
    assert body["official_equivalence_enabled"] is False

    result = next(r for r in body["results"] if r["construct_id"] == dimension["id"])
    assert result["suppressed"] is False
    assert result["n_valid"] == 3
    # Con LOWER_BETTER: P1=5(REVERSE en P2 lo compensa) — el punto clave es
    # que el pipeline corrió de extremo a extremo con datos coherentes.
    # "BAREMED" (motor canónico ScoringService) reemplaza al antiguo
    # "PROVISIONAL" del motor CENSOPAS retirado — la corrida sí tiene barem.
    assert result["classification_status"] == "BAREMED"
    assert result["favorable_n"] + result["intermediate_n"] + result["unfavorable_n"] == 3


async def test_censopas_unit_results_apply_secondary_suppression(
    client: AsyncClient, seed_user, seed_project
) -> None:
    study, _dimension = await _setup_censopas_study(
        client,
        seed_user,
        seed_project,
        min_publishable_n=2,
        with_units=True,
    )
    scoring_resp = await client.post(
        f"/api/v1/studies/{study['id']}/censopas/scoring"
    )
    assert scoring_resp.status_code == 200, scoring_resp.text

    response = await client.get(
        f"/api/v1/studies/{study['id']}/censopas/unit-results",
        params={"unit_type_id": study["_test_unit_type_id"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["secondary_suppression_applied"] is True
    assert len(body["results"]) == 2
    assert all(result["suppressed"] for result in body["results"])
    assert {result["suppression_reason"] for result in body["results"]} == {
        "BELOW_MINIMUM_N",
        "SECONDARY_DEDUCTION_PROTECTION",
    }


async def test_censopas_unit_results_group_small_units_under_publishable_parent(
    client: AsyncClient, seed_user, seed_project
) -> None:
    """Contabilidad (3) y Tesorería (4) no alcanzan min_publishable_n=5 por
    separado, pero agrupadas bajo "Administración financiera" (parent_id)
    suman 7 y sí son publicables — sin exponer las celdas individuales."""
    study, _dimension = await _setup_censopas_study(
        client,
        seed_user,
        seed_project,
        min_publishable_n=5,
        create_sessions=False,
        unit_specs=[
            {"code": "ADMIN_FIN", "name": "Administración financiera"},
            {"code": "CONTABILIDAD", "name": "Contabilidad", "parent_code": "ADMIN_FIN"},
            {"code": "TESORERIA", "name": "Tesorería", "parent_code": "ADMIN_FIN"},
        ],
    )
    unit_type_id = study["_test_unit_type_id"]
    units_by_code = study["_test_units_by_code"]
    parent = units_by_code["ADMIN_FIN"]
    contabilidad = units_by_code["CONTABILIDAD"]
    tesoreria = units_by_code["TESORERIA"]

    items_by_code = {
        item["code"]: item
        for item in (
            await client.get(f"/api/v1/instrument-versions/{study['instrument_version_id']}/items")
        ).json()
    }
    item1 = items_by_code["P1"]
    item2 = items_by_code["P2"]

    session_units = [contabilidad["id"]] * 3 + [tesoreria["id"]] * 4
    for unit_id in session_units:
        rs = (await client.post(f"/api/v1/studies/{study['id']}/response-sessions")).json()
        await client.put(
            f"/api/v1/response-sessions/{rs['id']}/units",
            json={"unit_ids": [unit_id]},
        )
        await client.put(
            f"/api/v1/response-sessions/{rs['id']}/responses/{item1['id']}",
            json={"raw_code": "5"},
        )
        await client.put(
            f"/api/v1/response-sessions/{rs['id']}/responses/{item2['id']}",
            json={"raw_code": "1"},
        )
        await client.post(f"/api/v1/response-sessions/{rs['id']}/complete")

    scoring_resp = await client.post(f"/api/v1/studies/{study['id']}/censopas/scoring")
    assert scoring_resp.status_code == 200, scoring_resp.text

    response = await client.get(
        f"/api/v1/studies/{study['id']}/censopas/unit-results",
        params={"unit_type_id": unit_type_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    unit_ids_in_response = {result["unit_id"] for result in body["results"]}
    assert contabilidad["id"] not in unit_ids_in_response
    assert tesoreria["id"] not in unit_ids_in_response
    assert parent["id"] in unit_ids_in_response

    parent_result = next(r for r in body["results"] if r["unit_id"] == parent["id"])
    assert parent_result["n_valid"] == 7
    assert parent_result["suppressed"] is False
    assert parent_result["suppression_reason"] is None
    assert set(parent_result["grouped_units"]) == {"Contabilidad", "Tesorería"}


async def test_censopas_results_suppressed_below_min_publishable_n(
    client: AsyncClient, seed_user, seed_project
) -> None:
    study, dimension = await _setup_censopas_study(client, seed_user, seed_project, min_publishable_n=5)

    await client.post(f"/api/v1/studies/{study['id']}/censopas/scoring")
    results_resp = await client.get(f"/api/v1/studies/{study['id']}/censopas/results")
    body = results_resp.json()

    result = next(r for r in body["results"] if r["construct_id"] == dimension["id"])
    assert result["suppressed"] is True
    assert result["n_valid"] == 3
    assert result["favorable_n"] is None
    assert result["construct_score"] is None


async def test_general_scoring_materializes_construct_variable_for_generic_analytics(
    client: AsyncClient, seed_user, seed_project
) -> None:
    study, dimension = await _setup_censopas_study(
        client, seed_user, seed_project, min_publishable_n=1
    )

    scoring_resp = await client.post(f"/api/v1/studies/{study['id']}/scoring")
    assert scoring_resp.status_code == 200, scoring_resp.text
    assert scoring_resp.json()["constructs_scored"] == 2

    overview_resp = await client.get(f"/api/v1/studies/{study['id']}/results/overview")
    assert overview_resp.status_code == 200, overview_resp.text
    assert overview_resp.json()["instrument_name"] == "CENSOPAS test"
    assert overview_resp.json()["instrument_id"] is not None

    project_root = (await client.get(
        f"/api/v1/instrument-versions/{study['instrument_version_id']}/tree"
    )).json()["variables"][0]

    variables_resp = await client.get(
        f"/api/v1/projects/{seed_project.id}/variables?page_size=100"
    )
    assert variables_resp.status_code == 200, variables_resp.text
    construct_variables = [
        item
        for item in variables_resp.json()["items"]
        if item["construct_id"] == project_root["id"]
    ]
    assert len(construct_variables) == 1
    variable = construct_variables[0]
    assert variable["variable_type"] == "CONSTRUCT_SCORE"
    assert variable["measurement_level"] == "SCALE"
    assert variable["data_type"] == "DECIMAL"
    assert variable["is_editable"] is False

    describe_resp = await client.post(
        f"/api/v1/studies/{study['id']}/analytics/describe",
        json={"variable_ids": [variable["id"]]},
    )
    assert describe_resp.status_code == 200, describe_resp.text
    descriptive = describe_resp.json()["results"][0]
    assert descriptive["construct_id"] == project_root["id"]
    assert descriptive["n_valid"] == 3

    correlation_resp = await client.post(
        f"/api/v1/studies/{study['id']}/analytics/correlation",
        json={"variable_x_id": variable["id"], "variable_y_id": variable["id"]},
    )
    assert correlation_resp.status_code == 200, correlation_resp.text
    assert correlation_resp.json()["results"][0]["n_valid"] == 3

    second_scoring_resp = await client.post(f"/api/v1/studies/{study['id']}/scoring")
    assert second_scoring_resp.status_code == 200, second_scoring_resp.text
    variables_resp = await client.get(
        f"/api/v1/projects/{seed_project.id}/variables?page_size=100"
    )
    construct_variables = [
        item
        for item in variables_resp.json()["items"]
        if item["construct_id"] == project_root["id"]
    ]
    assert len(construct_variables) == 1


async def test_censopas_scoring_fails_when_scoring_rule_missing(
    client: AsyncClient, seed_user, seed_project
) -> None:
    study, _dimension = await _setup_censopas_study(
        client, seed_user, seed_project, min_publishable_n=1, create_scoring_rules=False
    )

    scoring_resp = await client.post(f"/api/v1/studies/{study['id']}/censopas/scoring")
    assert scoring_resp.status_code == 422, scoring_resp.text
    body = scoring_resp.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert body["missing_scoring_rules"]

    results_resp = await client.get(f"/api/v1/studies/{study['id']}/censopas/results")
    assert results_resp.status_code == 409, results_resp.text
    conflict_body = results_resp.json()
    assert conflict_body["latest_run_status"] == "FAILED"
    assert conflict_body["missing"]


async def test_censopas_results_conflict_when_never_run(
    client: AsyncClient, seed_user, seed_project
) -> None:
    study, _dimension = await _setup_censopas_study(client, seed_user, seed_project, min_publishable_n=1)

    results_resp = await client.get(f"/api/v1/studies/{study['id']}/censopas/results")
    assert results_resp.status_code == 409, results_resp.text
    body = results_resp.json()
    assert body["latest_run_status"] is None
    assert body["missing"]


async def test_censopas_scoring_fails_when_no_valid_sessions(
    client: AsyncClient, seed_user, seed_project
) -> None:
    study, _dimension = await _setup_censopas_study(
        client, seed_user, seed_project, min_publishable_n=1, create_sessions=False
    )

    scoring_resp = await client.post(f"/api/v1/studies/{study['id']}/censopas/scoring")
    assert scoring_resp.status_code == 422, scoring_resp.text
    assert scoring_resp.json()["error_code"] == "INSUFFICIENT_SAMPLE"


async def test_activate_barem_returns_422_when_incomplete(
    client: AsyncClient, seed_user, seed_project
) -> None:
    instrument = (
        await client.post(
            "/api/v1/instruments", json={"name": "Barem incompleto", "is_system": False}
        )
    ).json()
    version = (
        await client.post(
            f"/api/v1/instruments/{instrument['id']}/versions",
            json={"version_code": "V1", "status": "DRAFT"},
        )
    ).json()
    barem = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/barems",
            json={"name": "Barem sin niveles"},
        )
    ).json()

    activate_resp = await client.post(f"/api/v1/barems/{barem['id']}/activate")
    assert activate_resp.status_code == 422, activate_resp.text
    body = activate_resp.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert body["validations"]
    assert body["status"] == "DRAFT"

    list_resp = await client.get(f"/api/v1/instrument-versions/{version['id']}/barems")
    assert list_resp.json()[0]["status"] == "DRAFT"


async def test_activate_barem_succeeds_when_complete(
    client: AsyncClient, seed_user, seed_project
) -> None:
    instrument = (
        await client.post(
            "/api/v1/instruments", json={"name": "Barem completo", "is_system": False}
        )
    ).json()
    version = (
        await client.post(
            f"/api/v1/instruments/{instrument['id']}/versions",
            json={"version_code": "V1", "status": "DRAFT"},
        )
    ).json()
    project_root = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/structure-variables",
            json={"code": "VAR", "name": "Variable", "role": "OUTCOME"},
        )
    ).json()
    dimension = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/constructs",
            json={
                "parent_id": project_root["id"],
                "code": "D1",
                "name": "Dimensión",
                "construct_type": "DIMENSION",
            },
        )
    ).json()
    barem = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/barems",
            json={
                "name": "Barem completo",
                "source_reference": "Manual técnico v1",
                "population_label": "Población de referencia",
                "barem_version": "1.0",
            },
        )
    ).json()
    await client.put(
        f"/api/v1/barems/{barem['id']}/bands",
        json={
            "bands": [
                {
                    "construct_id": project_root["id"],
                    "code": "BAJO",
                    "label": "Bajo",
                    "min_value": 0,
                    "max_value": 50,
                    "severity_order": 1,
                },
                {
                    "construct_id": project_root["id"],
                    "code": "ALTO",
                    "label": "Alto",
                    "min_value": 50,
                    "max_value": 100,
                    "severity_order": 2,
                },
            ]
        },
    )

    activate_resp = await client.post(f"/api/v1/barems/{barem['id']}/activate")
    assert activate_resp.status_code == 200, activate_resp.text
    body = activate_resp.json()
    assert body["activated"] is True
    assert body["status"] == "ACTIVE"
    assert body["validations"] == []


async def test_generated_barem_targets_only_project_root_and_can_copy_for_editing(
    client: AsyncClient, seed_user, seed_project
) -> None:
    instrument = (
        await client.post(
            "/api/v1/instruments", json={"name": "Baremo por variables", "is_system": False}
        )
    ).json()
    version = (
        await client.post(
            f"/api/v1/instruments/{instrument['id']}/versions",
            json={"version_code": "V1", "status": "DRAFT"},
        )
    ).json()
    project_root = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/structure-variables",
            json={"code": "VAR", "name": "Variable", "role": "OUTCOME"},
        )
    ).json()
    root = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/constructs",
            json={
                "parent_id": project_root["id"],
                "code": "DIM_1",
                "name": "Dimensión 1",
                "construct_type": "DIMENSION",
            },
        )
    ).json()
    child = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/constructs",
            json={
                "parent_id": root["id"],
                "code": "SUB_1",
                "name": "Subdimensión 1",
                "construct_type": "SUBDIMENSION",
            },
        )
    ).json()
    barem = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/barems",
            json={
                "name": "Baremo raíz",
                "source_reference": "Manual técnico",
                "population_label": "Población objetivo",
                "barem_version": "1.0",
            },
        )
    ).json()

    generated_resp = await client.post(
        f"/api/v1/barems/{barem['id']}/generate-bands",
        json={"levels": 3, "method": "EQUAL_INTERVAL", "direction": "HIGHER_BETTER"},
    )
    assert generated_resp.status_code == 200, generated_resp.text
    generated = generated_resp.json()
    assert len(generated["bands"]) == 3
    assert {band["construct_id"] for band in generated["bands"]} == {project_root["id"]}
    assert child["id"] not in {band["construct_id"] for band in generated["bands"]}

    activate_resp = await client.post(f"/api/v1/barems/{barem['id']}/activate")
    assert activate_resp.status_code == 200, activate_resp.text

    copy_resp = await client.post(
        f"/api/v1/barems/{barem['id']}/editable-copy", json={}
    )
    assert copy_resp.status_code == 201, copy_resp.text
    editable_copy = copy_resp.json()
    assert editable_copy["status"] == "DRAFT"
    assert len(editable_copy["bands"]) == 3
    assert {band["construct_id"] for band in editable_copy["bands"]} == {project_root["id"]}


async def test_readiness_does_not_require_items_on_dimensions_with_subdimensions(
    client: AsyncClient,
) -> None:
    """DIMENSION -> SUBDIMENSION -> ITEM: items are linked at the leaf
    (subdimension) level only, per how the Constructor UI models CENSOPAS
    Media. A dimension that rolls up through subdimensions must not be
    required to hold direct item_links itself, or every such instrument
    trips EMPTY_SCORING_CONSTRUCTS despite full item coverage."""
    instrument = (
        await client.post(
            "/api/v1/instruments", json={"name": "CENSOPAS jerarquía test", "is_system": False}
        )
    ).json()
    version = (
        await client.post(
            f"/api/v1/instruments/{instrument['id']}/versions",
            json={
                "version_code": "V1",
                "status": "DRAFT",
                "config": {"censopas_version_kind": "MEDIUM"},
            },
        )
    ).json()

    variable = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/structure-variables",
            json={"code": "CENSOPAS", "name": "CENSOPAS", "role": "OUTCOME"},
        )
    ).json()
    dimension = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/constructs",
            json={
                "parent_id": variable["id"],
                "code": "D1",
                "name": "Exigencias psicológicas",
                "construct_type": "DIMENSION",
            },
        )
    ).json()
    subdimension = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/constructs",
            json={
                "parent_id": dimension["id"],
                "code": "S1",
                "name": "Ritmo de trabajo",
                "construct_type": "SUBDIMENSION",
            },
        )
    ).json()

    item = (
        await client.post(
            f"/api/v1/instrument-versions/{version['id']}/items",
            json={
                "code": "P1",
                "question_text": "Ritmo de trabajo",
                "question_type": "LIKERT",
                "is_scored": True,
            },
        )
    ).json()
    link_resp = await client.post(
        f"/api/v1/constructs/{subdimension['id']}/items",
        json={"question_id": item["id"], "weight": 1, "scoring_direction": "DIRECT"},
    )
    assert link_resp.status_code == 201, link_resp.text
    await client.post(
        f"/api/v1/instrument-versions/{version['id']}/scoring-rules",
        json={
            "question_id": item["id"],
            "parameters": {"map": {"1": 0, "2": 25, "3": 50, "4": 75, "5": 100}},
            "status": "VALIDATED",
        },
    )

    readiness_resp = await client.get(
        f"/api/v1/instrument-versions/{version['id']}/censopas/readiness"
    )
    assert readiness_resp.status_code == 200, readiness_resp.text
    body = readiness_resp.json()
    assert "EMPTY_SCORING_CONSTRUCTS" not in body["errors"]
