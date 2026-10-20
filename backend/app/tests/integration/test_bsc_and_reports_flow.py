"""Flujo Fase 9 (BSC + reportes)."""

import json

from httpx import AsyncClient


async def _second_study(client: AsyncClient, seed_user, seed_project, version_id: int):
    """Segundo estudio sobre la misma versión de instrumento, sin agregar
    ítems nuevos (la versión ya queda bloqueada para edición en cuanto el
    primer estudio abre sesiones de respuesta)."""
    survey = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/surveys/from-instrument",
            json={
                "created_by_user_id": seed_user.id,
                "instrument_version_id": version_id,
                "name": "Encuesta BSC 2",
            },
        )
    ).json()
    study = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/studies",
            json={"survey_id": survey["id"], "name": "Estudio BSC 2", "study_type": "ACADEMIC"},
        )
    ).json()
    await client.post(f"/api/v1/studies/{study['id']}/open")
    return study


async def _basic_study(client: AsyncClient, seed_user, seed_project, seed_instrument_draft):
    _instrument, version = seed_instrument_draft
    item = (
        await client.post(
            f"/api/v1/instrument-versions/{version.id}/items",
            json={"code": "P1", "question_text": "P1", "question_type": "NUMBER"},
        )
    ).json()
    var = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/variables",
            json={
                "code": "p1",
                "name": "P1",
                "variable_type": "QUESTION",
                "data_type": "INTEGER",
                "measurement_level": "SCALE",
                "question_id": item["id"],
            },
        )
    ).json()
    survey = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/surveys/from-instrument",
            json={
                "created_by_user_id": seed_user.id,
                "instrument_version_id": version.id,
                "name": "Encuesta BSC",
            },
        )
    ).json()
    study = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/studies",
            json={"survey_id": survey["id"], "name": "Estudio BSC", "study_type": "ACADEMIC"},
        )
    ).json()
    await client.post(f"/api/v1/studies/{study['id']}/open")
    for value in (1, 2, 3, 4, 5):
        rs = (await client.post(f"/api/v1/studies/{study['id']}/response-sessions")).json()
        await client.put(
            f"/api/v1/response-sessions/{rs['id']}/responses/{item['id']}",
            json={"numeric_value": value},
        )
        await client.post(f"/api/v1/response-sessions/{rs['id']}/complete")
    return study, var


async def test_action_plan_and_kpi_lifecycle(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, _var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)

    plan_resp = await client.post(
        f"/api/v1/studies/{study['id']}/action-plans", json={"name": "Plan preventivo 2026"}
    )
    assert plan_resp.status_code == 201
    plan = plan_resp.json()

    item_resp = await client.post(
        f"/api/v1/action-plans/{plan['id']}/items",
        json={
            "title": "Capacitación en gestión del tiempo",
            "action_description": "Taller mensual para el área comercial.",
            "priority": 1,
        },
    )
    assert item_resp.status_code == 201
    item = item_resp.json()
    assert item["status"] == "PENDING"

    update_resp = await client.patch(
        f"/api/v1/action-plan-items/{item['id']}", json={"status": "IN_PROGRESS"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "IN_PROGRESS"

    kpi_resp = await client.post(
        f"/api/v1/studies/{study['id']}/kpis",
        json={"name": "% asistencia a talleres", "target_value": 90, "unit": "%"},
    )
    assert kpi_resp.status_code == 201
    kpi = kpi_resp.json()

    measurement_resp = await client.post(
        f"/api/v1/kpis/{kpi['id']}/measurements",
        json={"measured_at": "2026-03-01T00:00:00Z", "numeric_value": 75},
    )
    assert measurement_resp.status_code == 201

    measurements_resp = await client.get(f"/api/v1/kpis/{kpi['id']}/measurements")
    assert measurements_resp.status_code == 200
    assert len(measurements_resp.json()) == 1


async def test_report_generation_bundles_analysis_results(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)

    describe_resp = await client.post(
        f"/api/v1/studies/{study['id']}/analytics/describe", json={"variable_ids": [var["id"]]}
    )
    assert describe_resp.status_code == 200

    report_resp = await client.post(
        f"/api/v1/studies/{study['id']}/reports", json={"output_format": "JSON"}
    )
    assert report_resp.status_code == 201, report_resp.text
    report = report_resp.json()
    assert report["status"] == "COMPLETED"
    assert report["data_hash"] is not None

    download_resp = await client.get(f"/api/v1/reports/{report['id']}/download")
    assert download_resp.status_code == 200
    bundle = json.loads(download_resp.text)
    assert bundle["study"]["id"] == study["id"]
    assert len(bundle["analysis_results"]) == 1
    assert bundle["analysis_results"][0]["result_type"] == "DESCRIPTIVE"


async def test_report_generation_defaults_to_docx(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, _ = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)

    report_resp = await client.post(f"/api/v1/studies/{study['id']}/reports", json={})
    assert report_resp.status_code == 201, report_resp.text
    report = report_resp.json()
    assert report["status"] == "COMPLETED"
    assert report["output_format"] == "DOCX"

    download_resp = await client.get(f"/api/v1/reports/{report['id']}/download")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    # .docx es un contenedor ZIP — firma binaria estándar, prueba barata de
    # que efectivamente se generó un documento Word y no texto/JSON.
    assert download_resp.content[:4] == b"PK\x03\x04"

async def test_report_generation_supports_pdf(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, _ = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)

    report_resp = await client.post(
        f"/api/v1/studies/{study['id']}/reports",
        json={"output_format": "PDF", "report_mode": "PROVISIONAL"},
    )
    assert report_resp.status_code == 201, report_resp.text
    report = report_resp.json()
    assert report["status"] == "COMPLETED"
    assert report["output_format"] == "PDF"

    download_resp = await client.get(f"/api/v1/reports/{report['id']}/download")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/pdf"
    assert download_resp.content[:5] == b"%PDF-"


async def test_report_preview_reuses_same_docx_for_download(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    """El preview siempre genera un DOCX (sin importar `output_format`
    pedido) y el PDF de preview es una conversión de ese mismo archivo — el
    hash de `/download` debe coincidir con el hash con el que se calculó el
    PDF de preview: no hay una segunda generación al exportar."""
    study, _ = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)

    preview_resp = await client.post(
        f"/api/v1/studies/{study['id']}/reports/preview",
        json={"output_format": "PDF", "report_mode": "PROVISIONAL"},
    )
    assert preview_resp.status_code == 201, preview_resp.text
    preview = preview_resp.json()
    assert preview["status"] == "COMPLETED"
    assert preview["pages"] and preview["pages"] > 0
    assert preview["preview_url"] == f"/reports/{preview['preview_id']}/preview.pdf"

    preview_pdf_resp = await client.get(f"/api/v1/reports/{preview['preview_id']}/preview.pdf")
    assert preview_pdf_resp.status_code == 200
    assert preview_pdf_resp.headers["content-type"] == "application/pdf"
    assert preview_pdf_resp.content[:5] == b"%PDF-"

    pdf_download_resp = await client.get(
        f"/api/v1/reports/{preview['preview_id']}/download.pdf"
    )
    assert pdf_download_resp.status_code == 200
    assert pdf_download_resp.headers["content-type"] == "application/pdf"
    assert "attachment" in pdf_download_resp.headers["content-disposition"]
    assert pdf_download_resp.content[:5] == b"%PDF-"

    download_resp = await client.get(f"/api/v1/reports/{preview['preview_id']}/download")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert download_resp.content[:4] == b"PK\x03\x04"

    report_resp = await client.get(f"/api/v1/reports/{preview['preview_id']}")
    assert report_resp.status_code == 200
    # El `output_format="PDF"` pedido no se respeta al previsualizar: el
    # archivo canónico guardado siempre es el DOCX.
    assert report_resp.json()["output_format"] == "DOCX"


def test_report_serialization_removes_individual_payloads_recursively() -> None:
    from types import SimpleNamespace
    from app.services.report_service import ReportService

    result = SimpleNamespace(
        result_type="KMEANS", result_code="KM", n_valid=10,
        numeric_value=None, statistic_value=None, p_value=None,
        adjusted_p_value=None, effect_size=None, effect_label=None,
        ci_lower=None, ci_upper=None, text_value=None,
        result_data={
            "labels": [0, 1], "anonymous_token": "secret",
            "aggregate": {
                "points": [[1, 2]], "centroids": [[1.5, 2.5]],
                "cluster_sizes": [5, 5],
            },
        },
    )
    serialized = ReportService._serialize_result(result)
    assert "labels" not in serialized["result_data"]
    assert "anonymous_token" not in serialized["result_data"]
    assert "points" not in serialized["result_data"]["aggregate"]
    assert serialized["result_data"]["aggregate"]["cluster_sizes"] == [5, 5]


async def test_report_includes_action_plan_premium_and_traceability(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    from io import BytesIO
    from docx import Document

    study, var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)
    correlation = await client.post(
        "/api/v1/studies/{}/analytics/correlation".format(study["id"]),
        json={"variable_x_id": var["id"], "variable_y_id": var["id"]},
    )
    assert correlation.status_code == 200, correlation.text
    plan = (await client.post(
        "/api/v1/studies/{}/action-plans".format(study["id"]),
        json={"name": "Plan preventivo CENSOPAS"},
    )).json()
    item = (await client.post(
        "/api/v1/action-plans/{}/items".format(plan["id"]),
        json={
            "title": "Reducir exposición", "finding": "Prioridad preventiva",
            "action_description": "Implementar pausas y seguimiento mensual.",
            "responsible_user_id": seed_user.id, "responsible_label": "Comité SST",
            "priority": 1, "due_date": "2026-12-01",
        },
    )).json()
    kpi = (await client.post(
        "/api/v1/studies/{}/kpis".format(study["id"]),
        json={
            "action_plan_item_id": item["id"], "code": "KPI-01",
            "name": "Cumplimiento de pausas", "baseline_value": 40,
            "target_value": 90, "unit": "%",
        },
    )).json()
    measurement = await client.post(
        "/api/v1/kpis/{}/measurements".format(kpi["id"]),
        json={"measured_at": "2026-08-01T00:00:00Z", "numeric_value": 75},
    )
    assert measurement.status_code == 201

    sections = ["plan_accion", "hallazgos_premium", "anexos", "trazabilidad"]
    report_resp = await client.post(
        "/api/v1/studies/{}/reports".format(study["id"]),
        json={"output_format": "JSON", "sections": sections},
    )
    assert report_resp.status_code == 201, report_resp.text
    downloaded = await client.get(
        "/api/v1/reports/{}/download".format(report_resp.json()["id"])
    )
    bundle = json.loads(downloaded.text)
    action = bundle["action_plans"][0]["items"][0]
    assert action["responsible_label"] == "Comité SST"
    assert "responsible_user_id" not in action
    assert action["kpis"][0]["latest_measurement"]["numeric_value"] == 75.0
    assert bundle["premium_analytics"]["status"] == "AVAILABLE"
    assert "SPEARMAN" in bundle["premium_analytics"]["methods"]
    assert bundle["traceability"]["lineage"][0] == "responses.raw_code"
    assert bundle["traceability"]["privacy"]["individual_records_included"] is False

    docx_resp = await client.post(
        "/api/v1/studies/{}/reports".format(study["id"]),
        json={"output_format": "DOCX", "sections": sections},
    )
    assert docx_resp.status_code == 201, docx_resp.text
    docx_download = await client.get(
        "/api/v1/reports/{}/download".format(docx_resp.json()["id"])
    )
    document = Document(BytesIO(docx_download.content))
    text_content = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Plan de acción y seguimiento" in text_content
    assert "Analítica premium" in text_content
    assert "Anexo de trazabilidad" in text_content

    pdf_resp = await client.post(
        "/api/v1/studies/{}/reports".format(study["id"]),
        json={"output_format": "PDF", "sections": sections},
    )
    assert pdf_resp.status_code == 201, pdf_resp.text
    pdf_download = await client.get(
        "/api/v1/reports/{}/download".format(pdf_resp.json()["id"])
    )
    assert pdf_download.content[:5] == b"%PDF-"


async def _plan_and_item(client: AsyncClient, study_id: int, **item_kwargs):
    plan = (
        await client.post(
            f"/api/v1/studies/{study_id}/action-plans", json={"name": "Plan preventivo"}
        )
    ).json()
    payload = {"title": "Acción", "action_description": "Medida preventiva"} | item_kwargs
    item = (await client.post(f"/api/v1/action-plans/{plan['id']}/items", json=payload)).json()
    return plan, item


async def test_kpi_queda_vinculado_a_action_plan_item(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, _var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)
    _plan, item = await _plan_and_item(client, study["id"])

    kpi = (
        await client.post(
            f"/api/v1/studies/{study['id']}/kpis",
            json={"action_plan_item_id": item["id"], "name": "Cumplimiento"},
        )
    ).json()
    assert kpi["action_plan_item_id"] == item["id"]

    kpis = (await client.get(f"/api/v1/studies/{study['id']}/kpis")).json()
    assert kpis[0]["action_plan_item_id"] == item["id"]


async def test_origin_hypothesis_round_trip(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, _var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)
    _plan, item = await _plan_and_item(
        client,
        study["id"],
        finding="Alta exposición en D1",
        origin_hypothesis="Carga elevada, plazos cortos o interrupciones.",
        action_description="Redistribuir la carga semanal.",
    )
    assert item["finding"] == "Alta exposición en D1"
    assert item["origin_hypothesis"] == "Carga elevada, plazos cortos o interrupciones."
    assert item["action_description"] == "Redistribuir la carga semanal."
    # Los tres campos permanecen separados, no fusionados en uno solo.
    assert item["finding"] != item["origin_hypothesis"] != item["action_description"]


async def test_analysis_run_id_round_trip(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)
    correlation = await client.post(
        f"/api/v1/studies/{study['id']}/analytics/correlation",
        json={"variable_x_id": var["id"], "variable_y_id": var["id"]},
    )
    run_id = correlation.json()["id"]

    _plan, item = await _plan_and_item(client, study["id"], analysis_run_id=run_id)
    assert item["analysis_run_id"] == run_id


async def test_analysis_run_id_de_otro_estudio_es_rechazado(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    _instrument, version = seed_instrument_draft
    study, var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)
    other_study = await _second_study(client, seed_user, seed_project, version.id)
    for value in (1, 2, 3):
        rs = (await client.post(f"/api/v1/studies/{other_study['id']}/response-sessions")).json()
        await client.put(
            f"/api/v1/response-sessions/{rs['id']}/responses/1", json={"numeric_value": value}
        )
        await client.post(f"/api/v1/response-sessions/{rs['id']}/complete")
    correlation = await client.post(
        f"/api/v1/studies/{other_study['id']}/analytics/correlation",
        json={"variable_x_id": var["id"], "variable_y_id": var["id"]},
    )
    run_id = correlation.json()["id"]

    plan = (
        await client.post(
            f"/api/v1/studies/{study['id']}/action-plans", json={"name": "Plan preventivo"}
        )
    ).json()
    resp = await client.post(
        f"/api/v1/action-plans/{plan['id']}/items",
        json={
            "title": "Acción",
            "action_description": "Medida",
            "analysis_run_id": run_id,
        },
    )
    assert resp.status_code == 422


async def test_kpi_current_value_es_la_ultima_medicion(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, _var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)
    kpi = (
        await client.post(f"/api/v1/studies/{study['id']}/kpis", json={"name": "% asistencia"})
    ).json()
    assert kpi["current_value"] is None

    await client.post(
        f"/api/v1/kpis/{kpi['id']}/measurements",
        json={"measured_at": "2026-01-01T00:00:00Z", "numeric_value": 40},
    )
    await client.post(
        f"/api/v1/kpis/{kpi['id']}/measurements",
        json={"measured_at": "2026-06-01T00:00:00Z", "numeric_value": 75},
    )

    kpis = (await client.get(f"/api/v1/studies/{study['id']}/kpis")).json()
    assert kpis[0]["current_value"] == 75.0
    assert kpis[0]["current_measurement_at"].startswith("2026-06-01")


async def test_effective_status_overdue(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, _var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)
    _plan, item = await _plan_and_item(client, study["id"], due_date="2020-01-01")
    assert item["status"] == "PENDING"
    assert item["effective_status"] == "OVERDUE"


async def test_done_nunca_se_convierte_en_overdue(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, _var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)
    _plan, item = await _plan_and_item(client, study["id"], due_date="2020-01-01")

    updated = (
        await client.patch(f"/api/v1/action-plan-items/{item['id']}", json={"status": "DONE"})
    ).json()
    assert updated["status"] == "DONE"
    assert updated["effective_status"] == "DONE"


async def test_accion_no_transporta_valores_de_resultado_suprimido(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    """El contrato de creación de acciones no tiene ningún campo de porcentaje
    o conteo: aunque un cliente intente enviarlos, Pydantic los ignora (no
    hay forma de que un valor suprimido llegue a `ActionPlanItem`)."""
    study, _var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)
    plan = (
        await client.post(
            f"/api/v1/studies/{study['id']}/action-plans", json={"name": "Plan preventivo"}
        )
    ).json()
    resp = await client.post(
        f"/api/v1/action-plans/{plan['id']}/items",
        json={
            "title": "Medida organizacional genérica",
            "action_description": "Redistribuir carga del área.",
            "finding": "Prioridad preventiva D1",
            "unfavorable_pct": 44.4,
            "n_valid": 3,
            "suppressed": True,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "unfavorable_pct" not in body
    assert "n_valid" not in body
    assert "suppressed" not in body


async def test_varias_acciones_por_el_mismo_constructo(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, _var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)
    plan = (
        await client.post(
            f"/api/v1/studies/{study['id']}/action-plans", json={"name": "Plan preventivo"}
        )
    ).json()
    for title in ("Acción A", "Acción B", "Acción C"):
        await client.post(
            f"/api/v1/action-plans/{plan['id']}/items",
            json={"title": title, "action_description": "Medida", "construct_id": 1},
        )
    items = (await client.get(f"/api/v1/action-plans/{plan['id']}/items")).json()
    assert len({item["id"] for item in items}) == 3
    assert all(item["construct_id"] == 1 for item in items)


async def test_varios_kpi_por_la_misma_accion(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, _var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)
    _plan, item = await _plan_and_item(client, study["id"])
    for name in ("% asistencia", "Horas extra promedio"):
        await client.post(
            f"/api/v1/studies/{study['id']}/kpis",
            json={"action_plan_item_id": item["id"], "name": name},
        )
    kpis = (await client.get(f"/api/v1/studies/{study['id']}/kpis")).json()
    assert len(kpis) == 2
    assert all(kpi["action_plan_item_id"] == item["id"] for kpi in kpis)


async def test_report_conserva_campos_nuevos_del_plan_preventivo(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study, var = await _basic_study(client, seed_user, seed_project, seed_instrument_draft)
    correlation = await client.post(
        f"/api/v1/studies/{study['id']}/analytics/correlation",
        json={"variable_x_id": var["id"], "variable_y_id": var["id"]},
    )
    run_id = correlation.json()["id"]

    _plan, item = await _plan_and_item(
        client,
        study["id"],
        finding="Alta exposición en D1",
        origin_hypothesis="Carga elevada.",
        analysis_run_id=run_id,
        due_date="2020-01-01",
    )
    await client.post(
        f"/api/v1/studies/{study['id']}/kpis",
        json={"action_plan_item_id": item["id"], "name": "% asistencia", "target_value": 90},
    )
    kpis = (await client.get(f"/api/v1/studies/{study['id']}/kpis")).json()
    await client.post(
        f"/api/v1/kpis/{kpis[0]['id']}/measurements",
        json={"measured_at": "2026-06-01T00:00:00Z", "numeric_value": 75},
    )

    report_resp = await client.post(
        f"/api/v1/studies/{study['id']}/reports",
        json={"output_format": "JSON", "sections": ["plan_accion"]},
    )
    bundle = json.loads(
        (await client.get(f"/api/v1/reports/{report_resp.json()['id']}/download")).text
    )
    action = bundle["action_plans"][0]["items"][0]
    assert action["analysis_run_id"] == run_id
    assert action["origin_hypothesis"] == "Carga elevada."
    assert action["effective_status"] == "OVERDUE"
    assert action["kpis"][0]["current_value"] == 75.0
