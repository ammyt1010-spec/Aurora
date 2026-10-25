"""Report/dashboard parity is scoped to one completed scoring execution."""
import json
from io import BytesIO
from pypdf import PdfReader

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.analysis import AnalysisRun
from app.models.censopas import BaremBand
from app.models.report import ReportRun
from app.tests.integration.test_censopas_flow import _setup_censopas_study


@pytest.mark.asyncio
async def test_explicit_report_and_dashboard_keep_old_run(client, session, seed_user, seed_project):
    client.headers["Authorization"] = f"Bearer {create_access_token(seed_user.id)}"
    study, _ = await _setup_censopas_study(client, seed_user, seed_project, min_publishable_n=1)
    first = (await client.post(f"/api/v1/studies/{study['id']}/scoring")).json()
    second = (await client.post(f"/api/v1/studies/{study['id']}/scoring")).json()
    run_id = first['analysis_run_id']
    assert second['analysis_run_id'] != run_id
    response = await client.post(f"/api/v1/studies/{study['id']}/reports", json={
        "output_format": "JSON", "analysis_run_id": run_id,
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body['analysis_run_id'] == run_id
    downloaded = await client.get(f"/api/v1/reports/{body['id']}/download")
    bundle = json.loads(downloaded.content)
    assert bundle['traceability']['analysis_run_id'] == run_id
    assert bundle['barem_results']['analysis_run_id'] == run_id
    assert bundle['traceability']['context_integrity'] == 'VERIFIED'
    assert len(bundle['traceability']['analysis_runs']) == 1
    dashboard = await client.get(f"/api/v1/studies/{study['id']}/reports/executive-dashboard?analysis_run_id={run_id}")
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()['analysis_run_id'] == run_id
    assert dashboard.json()['scoring_sample_n'] == bundle['barem_results']['n_completed']
    stored = await session.get(ReportRun, body['id'])
    assert stored.metadata_['executive_snapshot']['analysis_run_id'] == run_id
    pdf_response = await client.post(f"/api/v1/studies/{study['id']}/reports", json={
        "output_format": "PDF", "scoring_run_id": run_id,
    })
    assert pdf_response.status_code == 201, pdf_response.text
    pdf_download = await client.get(f"/api/v1/reports/{pdf_response.json()['id']}/download")
    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf_download.content)).pages)
    assert f"Scoring #{run_id}" in pdf_text
    assert f"N scoring {bundle['barem_results']['n_completed']}" in pdf_text
    assert 'Ejecución de scoring' in pdf_text


@pytest.mark.asyncio
async def test_cross_study_and_changed_barem_are_rejected(client, session, seed_user, seed_project):
    client.headers["Authorization"] = f"Bearer {create_access_token(seed_user.id)}"
    study, _ = await _setup_censopas_study(client, seed_user, seed_project, min_publishable_n=1)
    other, _ = await _setup_censopas_study(client, seed_user, seed_project, min_publishable_n=1)
    scoring = (await client.post(f"/api/v1/studies/{study['id']}/scoring")).json()
    run_id = scoring['analysis_run_id']
    denied = await client.get(f"/api/v1/studies/{other['id']}/reports/executive-dashboard?analysis_run_id={run_id}")
    assert denied.status_code == 404
    denied = await client.post(f"/api/v1/studies/{other['id']}/reports", json={'output_format': 'JSON', 'analysis_run_id': run_id})
    assert denied.status_code == 404
    run = await session.get(AnalysisRun, run_id)
    band = (await session.execute(select(BaremBand).where(BaremBand.barem_id == run.parameters['barem_id']))).scalars().first()
    band.label = 'Changed after scoring'
    await session.commit()
    changed = await client.get(f"/api/v1/studies/{study['id']}/reports/executive-dashboard?analysis_run_id={run_id}")
    assert changed.status_code in (409, 422), changed.text
