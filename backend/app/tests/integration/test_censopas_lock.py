import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


@pytest.fixture(autouse=True)
def _auth_client(client: AsyncClient, seed_user):
    token = create_access_token(seed_user.id)
    client.headers["Authorization"] = f"Bearer {token}"


async def test_locked_censopas_version_rejects_new_construct(
    client: AsyncClient, seed_censopas_locked
) -> None:
    _instrument, version = seed_censopas_locked

    resp = await client.post(
        f"/api/v1/instrument-versions/{version.id}/constructs",
        json={"code": "D1", "name": "D1", "construct_type": "DIMENSION"},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["error_code"] == "SYSTEM_INSTRUMENT_LOCKED"
    assert body["editable"] is False


async def test_locked_censopas_tree_reports_not_editable(
    client: AsyncClient, seed_censopas_locked
) -> None:
    _instrument, version = seed_censopas_locked
    resp = await client.get(f"/api/v1/instrument-versions/{version.id}/tree")
    assert resp.status_code == 200
    body = resp.json()
    assert body["editable"] is False
    assert body["lock_reason"] == "SYSTEM_INSTRUMENT_LOCKED"


async def test_clone_is_always_allowed_even_when_locked(
    client: AsyncClient, seed_censopas_locked
) -> None:
    instrument, version = seed_censopas_locked

    clone_resp = await client.post(
        f"/api/v1/instruments/{instrument.id}/versions/{version.id}/clone",
        json={"version_code": "CUSTOM_V2", "version_name": "Versión personalizada"},
    )
    assert clone_resp.status_code == 201, clone_resp.text
    cloned = clone_resp.json()
    assert cloned["status"] == "DRAFT"
    variable = (
        await client.post(
            f"/api/v1/instrument-versions/{cloned['id']}/structure-variables",
            json={"code": "VAR", "name": "Variable"},
        )
    ).json()

    # La versión clonada, al estar en DRAFT, sí es editable.
    new_construct_resp = await client.post(
        f"/api/v1/instrument-versions/{cloned['id']}/constructs",
        json={"parent_id": variable["id"], "code": "D1", "name": "D1", "construct_type": "DIMENSION"},
    )
    assert new_construct_resp.status_code == 201

async def test_locked_censopas_readiness_reports_structural_gaps(
    client: AsyncClient, seed_censopas_locked
) -> None:
    _instrument, version = seed_censopas_locked
    response = await client.get(
        f"/api/v1/instrument-versions/{version.id}/censopas/readiness"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version_kind"] == "SHORT"
    assert body["expected"]["questions"] == 42
    assert body["expected"]["scored"] == 31
    assert body["expected"]["dimensions"] == 6
    assert body["ready_for_scoring"] is False
    assert "QUESTIONS_COUNT_MISMATCH" in body["errors"]
    assert "OFFICIAL_BAREM_NOT_AVAILABLE" in body["warnings"]

def _short_manifest_payload() -> dict:
    questions = [
        {
            "code": f"Q{index}",
            "source_code": f"P{index}",
            "question_text": f"Ítem psicosocial {index}",
            "question_type": "LIKERT",
            "is_scored": True,
            "option_set_code": "FREQ_1_5",
            "sort_order": index,
        }
        for index in range(1, 32)
    ]
    questions.extend(
        {
            "code": f"X{index}",
            "source_code": f"X{index}",
            "question_text": f"Variable descriptiva {index}",
            "question_type": "TEXT",
            "is_scored": False,
            "sort_order": 31 + index,
        }
        for index in range(1, 12)
    )
    dimensions = []
    start = 1
    sizes = [6, 5, 5, 5, 5, 5]
    for dimension_index, size in enumerate(sizes, start=1):
        dimensions.append(
            {
                "code": f"D{dimension_index}",
                "name": f"Dimensión {dimension_index}",
                "construct_type": "DIMENSION",
                "parent_code": "CENSOPAS",
                "sort_order": dimension_index,
                "items": [
                    {
                        "question_code": f"Q{item_index}",
                        "scoring_direction": "DIRECT",
                        "sort_order": item_index,
                    }
                    for item_index in range(start, start + size)
                ],
            }
        )
        start += size
    return {
        "version_kind": "SHORT",
        "manifest_version": "test-v1",
        "source_reference": "fixture sintético; no oficial",
        "scales": [
            {
                "code": "FREQ_1_5",
                "name": "Frecuencia impresa",
                "options": [
                    {
                        "raw_code": str(index),
                        "label": f"Opción {index}",
                        "numeric_value": index,
                        "sort_order": index,
                    }
                    for index in range(1, 6)
                ],
            }
        ],
        "questions": questions,
        "constructs": [
            {
                "code": "CENSOPAS",
                "name": "CENSOPAS-COPSOQ",
                "construct_type": "VARIABLE",
                "sort_order": 0,
            },
            *dimensions,
        ],
        "scoring_rules": [
            {
                "question_code": f"Q{index}",
                "risk_map": {str(value): value for value in range(1, 6)},
                "rule_version": "test-v1",
            }
            for index in range(1, 32)
        ],
    }


async def test_validate_and_import_short_manifest_transactionally(
    client: AsyncClient, seed_instrument_draft
) -> None:
    _instrument, version = seed_instrument_draft
    payload = _short_manifest_payload()

    validation_resp = await client.post(
        f"/api/v1/instrument-versions/{version.id}/validate-manifest",
        json=payload,
    )
    assert validation_resp.status_code == 200, validation_resp.text
    validation = validation_resp.json()
    assert validation["valid"] is True
    assert validation["actual"]["questions"] == 42
    assert len(validation["calculated_hash"]) == 64

    import_resp = await client.post(
        f"/api/v1/instrument-versions/{version.id}/import-manifest",
        json=payload,
    )
    assert import_resp.status_code == 201, import_resp.text
    imported = import_resp.json()
    assert imported["imported"] == {
        "scales": 1,
        "questions": 42,
        "constructs": 7,
        "scoring_rules": 31,
    }
    assert imported["readiness"]["ready_for_scoring"] is True
    assert imported["readiness"]["ready_for_official_reporting"] is False

    barem_payload = {
        "name": "Baremo oficial sintético",
        "barem_type": "OFFICIAL",
        "population_label": "Población patrón sintética",
        "source_reference": "fixture sintético; no oficial",
        "barem_version": "test-v1",
        "authority": "Autoridad de prueba",
        "cutoffs": [
            {
                "construct_code": f"D{index}",
                "cut_1": 30,
                "cut_2": 70,
                "direction": "LOWER_BETTER",
            }
            for index in range(1, 7)
        ],
    }
    barem_validation_resp = await client.post(
        f"/api/v1/instrument-versions/{version.id}/validate-barem-manifest",
        json=barem_payload,
    )
    assert barem_validation_resp.status_code == 200, barem_validation_resp.text
    assert barem_validation_resp.json()["valid"] is True

    barem_import_resp = await client.post(
        f"/api/v1/instrument-versions/{version.id}/import-barem-manifest",
        json=barem_payload,
    )
    assert barem_import_resp.status_code == 201, barem_import_resp.text
    imported_barem = barem_import_resp.json()
    assert imported_barem["status"] == "DRAFT"
    assert imported_barem["cutoffs_imported"] == 6

    # El motor de scoring ejecuta contra BaremBand, no contra BaremCutoff —
    # sin bandas derivadas un barem importado nunca produciría
    # favorable/intermedio/desfavorable al puntuar (ver auditoría Resultados).
    barems_resp = await client.get(f"/api/v1/instrument-versions/{version.id}/barems")
    assert barems_resp.status_code == 200, barems_resp.text
    imported = next(b for b in barems_resp.json() if b["id"] == imported_barem["barem_id"])
    assert len(imported["bands"]) == 18  # 6 cortes x 3 bandas (FAVORABLE/INTERMEDIATE/UNFAVORABLE)
    assert {band["classification_code"] for band in imported["bands"]} == {
        "FAVORABLE",
        "INTERMEDIATE",
        "UNFAVORABLE",
    }

    activation_resp = await client.post(
        f"/api/v1/barems/{imported_barem['barem_id']}/activate"
    )
    assert activation_resp.status_code == 200, activation_resp.text
    assert activation_resp.json()["status"] == "ACTIVE"

    second_resp = await client.post(
        f"/api/v1/instrument-versions/{version.id}/import-manifest",
        json=payload,
    )
    assert second_resp.status_code == 409
