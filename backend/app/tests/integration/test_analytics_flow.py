"""Flujo Fase 5 (analytics básicos): describe, frequencies, crosstab,
available-methods, analysis-runs genérico (harness §21-23, §33-35, §46, §59).
"""

from httpx import AsyncClient


async def _setup_study_with_two_respondents(client: AsyncClient, seed_user, seed_project, version):
    age_item = (
        await client.post(
            f"/api/v1/instrument-versions/{version.id}/items",
            json={"code": "EDAD", "question_text": "Edad", "question_type": "NUMBER"},
        )
    ).json()
    sex_item = (
        await client.post(
            f"/api/v1/instrument-versions/{version.id}/items",
            json={"code": "SEXO", "question_text": "Sexo", "question_type": "SINGLE_CHOICE"},
        )
    ).json()

    age_var = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/variables",
            json={
                "code": "edad",
                "name": "Edad",
                "variable_type": "QUESTION",
                "data_type": "INTEGER",
                "measurement_level": "SCALE",
                "question_id": age_item["id"],
            },
        )
    ).json()
    sex_var = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/variables",
            json={
                "code": "sexo",
                "name": "Sexo",
                "variable_type": "QUESTION",
                "data_type": "CATEGORY",
                "measurement_level": "NOMINAL",
                "question_id": sex_item["id"],
            },
        )
    ).json()

    survey = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/surveys/from-instrument",
            json={
                "created_by_user_id": seed_user.id,
                "instrument_version_id": version.id,
                "name": "Encuesta analytics",
            },
        )
    ).json()
    study = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/studies",
            json={"survey_id": survey["id"], "name": "Estudio analytics", "study_type": "ACADEMIC"},
        )
    ).json()
    await client.post(f"/api/v1/studies/{study['id']}/open")

    respondents = [(20, "M"), (30, "F"), (40, "F")]
    for age, sex in respondents:
        rs = (
            await client.post(f"/api/v1/studies/{study['id']}/response-sessions")
        ).json()
        await client.put(
            f"/api/v1/response-sessions/{rs['id']}/responses/{age_item['id']}",
            json={"numeric_value": age},
        )
        await client.put(
            f"/api/v1/response-sessions/{rs['id']}/responses/{sex_item['id']}",
            json={"raw_code": sex},
        )
        await client.post(f"/api/v1/response-sessions/{rs['id']}/complete")

    return study, age_var, sex_var


async def test_describe_computes_stats_for_scale_variable(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    _instrument, version = seed_instrument_draft
    study, age_var, _sex_var = await _setup_study_with_two_respondents(
        client, seed_user, seed_project, version
    )

    resp = await client.post(
        f"/api/v1/studies/{study['id']}/analytics/describe",
        json={"variable_ids": [age_var["id"]]},
    )
    assert resp.status_code == 200, resp.text
    run = resp.json()
    assert run["status"] == "COMPLETED"
    assert len(run["results"]) == 1
    result = run["results"][0]
    assert result["result_type"] == "DESCRIPTIVE"
    assert result["n_valid"] == 3
    assert result["result_data"]["mean"] == 30.0


async def test_describe_rejects_nominal_variable(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    _instrument, version = seed_instrument_draft
    study, _age_var, sex_var = await _setup_study_with_two_respondents(
        client, seed_user, seed_project, version
    )

    resp = await client.post(
        f"/api/v1/studies/{study['id']}/analytics/describe",
        json={"variable_ids": [sex_var["id"]]},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "INVALID_ANALYSIS_ASSUMPTION"

    # El analysis_run debe quedar registrado como FAILED, no desaparecer.
    run_id_resp = await client.get(f"/api/v1/analysis-runs/1")
    assert run_id_resp.status_code == 200
    assert run_id_resp.json()["status"] == "FAILED"


async def test_frequencies_computes_categories(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    _instrument, version = seed_instrument_draft
    study, _age_var, sex_var = await _setup_study_with_two_respondents(
        client, seed_user, seed_project, version
    )

    resp = await client.post(
        f"/api/v1/studies/{study['id']}/analytics/frequencies",
        json={"variable_ids": [sex_var["id"]]},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["results"][0]
    categories = {c["value"]: c["n"] for c in result["result_data"]["categories"]}
    assert categories == {"F": 2, "M": 1}


async def test_crosstab_between_two_categorical_variables(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    _instrument, version = seed_instrument_draft

    sex_item = (
        await client.post(
            f"/api/v1/instrument-versions/{version.id}/items",
            json={"code": "SEXO", "question_text": "Sexo", "question_type": "SINGLE_CHOICE"},
        )
    ).json()
    group_item = (
        await client.post(
            f"/api/v1/instrument-versions/{version.id}/items",
            json={"code": "GRUPO", "question_text": "Grupo", "question_type": "SINGLE_CHOICE"},
        )
    ).json()
    sex_var = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/variables",
            json={
                "code": "sexo",
                "name": "Sexo",
                "variable_type": "QUESTION",
                "data_type": "CATEGORY",
                "measurement_level": "NOMINAL",
                "question_id": sex_item["id"],
            },
        )
    ).json()
    group_var = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/variables",
            json={
                "code": "grupo",
                "name": "Grupo",
                "variable_type": "QUESTION",
                "data_type": "CATEGORY",
                "measurement_level": "NOMINAL",
                "question_id": group_item["id"],
            },
        )
    ).json()
    survey = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/surveys/from-instrument",
            json={
                "created_by_user_id": seed_user.id,
                "instrument_version_id": version.id,
                "name": "Encuesta crosstab",
            },
        )
    ).json()
    study = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/studies",
            json={"survey_id": survey["id"], "name": "Estudio crosstab", "study_type": "ACADEMIC"},
        )
    ).json()
    await client.post(f"/api/v1/studies/{study['id']}/open")

    for sex, group in [("M", "A"), ("F", "A"), ("F", "B")]:
        rs = (await client.post(f"/api/v1/studies/{study['id']}/response-sessions")).json()
        await client.put(
            f"/api/v1/response-sessions/{rs['id']}/responses/{sex_item['id']}",
            json={"raw_code": sex},
        )
        await client.put(
            f"/api/v1/response-sessions/{rs['id']}/responses/{group_item['id']}",
            json={"raw_code": group},
        )

    resp = await client.post(
        f"/api/v1/studies/{study['id']}/analytics/crosstab",
        json={
            "row_variable_id": sex_var["id"],
            "column_variable_id": group_var["id"],
            "percentage_mode": "COUNT",
        },
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["results"][0]
    # The grand total is hidden to prevent reconstruction of censored cells.
    assert result["result_data"]["grand_total"] is None
    # E-05: min_publishable_n por defecto (5) supera los 3 respondentes del
    # fixture -> ninguna celda es publicable, todas quedan suprimidas.
    assert "raw_counts" not in result["result_data"]
    assert all(
        value is None
        for row in result["result_data"]["table"]
        for value in row["cells"].values()
    )


async def test_available_methods_by_measurement_level(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    _instrument, version = seed_instrument_draft
    study, age_var, sex_var = await _setup_study_with_two_respondents(
        client, seed_user, seed_project, version
    )

    scale_resp = await client.post(
        f"/api/v1/studies/{study['id']}/analytics/available-methods",
        json={"variable_ids": [age_var["id"]]},
    )
    assert scale_resp.json()["methods"] == ["DESCRIPTIVE"]

    categorical_resp = await client.post(
        f"/api/v1/studies/{study['id']}/analytics/available-methods",
        json={"variable_ids": [sex_var["id"]]},
    )
    assert categorical_resp.json()["methods"] == ["FREQUENCIES"]


async def test_generic_analysis_run_dispatch_and_unsupported_type(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    _instrument, version = seed_instrument_draft
    study, age_var, _sex_var = await _setup_study_with_two_respondents(
        client, seed_user, seed_project, version
    )

    ok_resp = await client.post(
        f"/api/v1/studies/{study['id']}/analysis-runs",
        json={"analysis_type": "DESCRIPTIVE", "parameters": {"variable_ids": [age_var["id"]]}},
    )
    assert ok_resp.status_code == 201
    assert ok_resp.json()["status"] == "COMPLETED"

    unsupported_resp = await client.post(
        f"/api/v1/studies/{study['id']}/analysis-runs",
        json={"analysis_type": "FACTOR_ANALYSIS", "parameters": {}},
    )
    assert unsupported_resp.status_code == 400
    assert unsupported_resp.json()["error_code"] == "UNSUPPORTED_ANALYSIS"

    # KMEANS sí está implementado (Fase 9), pero sin sus parámetros requeridos
    # debe fallar con un error de validación claro, no un 500 crudo.
    missing_params_resp = await client.post(
        f"/api/v1/studies/{study['id']}/analysis-runs",
        json={"analysis_type": "KMEANS", "parameters": {}},
    )
    assert missing_params_resp.status_code == 422
    assert missing_params_resp.json()["error_code"] == "VALIDATION_ERROR"
