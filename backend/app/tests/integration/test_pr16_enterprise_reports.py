"""Suite de pruebas de integración para el PR #16: Informes Profesionales Empresariales.

Verifica:
1. Catálogo y editor de plantillas de informe por disciplina (Psicosocial, Ergonomía, Clima).
2. Vista previa segura de muestra con marca de agua sin vulnerar bypass comercial.
3. Emisión definitiva atómica con orden pagada y trazabilidad criptográfica (data_hash SHA-256).
4. Dashboard ejecutivo con semáforos de riesgo y recomendaciones automáticas por disciplina.
5. Historial empresarial de informes con trazabilidad de emisor, orden y auditoría de descargas.
"""

from datetime import datetime, timedelta, UTC
from decimal import Decimal
import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.billing import ReportOrder, ReportTariff
from app.models.censopas import Barem, BaremBand
from app.models.construct import Construct, ConstructItem
from app.models.instrument import Instrument, InstrumentVersion
from app.models.option_set import OptionSet, OptionSetOption
from app.models.project import Project
from app.models.question import Question
from app.models.response import ResponseSession
from app.models.study import Study
from app.models.survey import Survey, SurveyQuestion
from app.models.user import Organization, OrganizationMembership
from app.schemas.responses import ResponseSessionCompleteRequest, ResponseUpsert
from app.schemas.studies import StudyCreate
from app.services.response_service import ResponseService
from app.services.scoring_service import ScoringService
from app.services.study_service import StudyService


@pytest.fixture
def auth_headers(seed_user):
    token = create_access_token(seed_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_pr16_multidisciplinary_template_catalog_and_editing(client: AsyncClient, session, seed_user, auth_headers, monkeypatch):
    """1. Catálogo de plantillas por disciplina y editor visual de configuración."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    seed_user.is_superuser = True
    await session.commit()

    # Listar plantillas generales (auto-siembra plantillas por defecto si está vacío)
    resp = await client.get("/api/v1/report-templates", headers=auth_headers)
    assert resp.status_code == 200
    templates = resp.json()
    assert len(templates) >= 3

    disciplines = {t["discipline"] for t in templates}
    assert "PSICOSOCIAL" in disciplines
    assert "ERGONOMIA" in disciplines
    assert "CLIMA" in disciplines

    # Filtrar por disciplina ERGONOMIA
    ergo_resp = await client.get("/api/v1/report-templates?discipline=ERGONOMIA", headers=auth_headers)
    assert ergo_resp.status_code == 200
    ergo_templates = ergo_resp.json()
    assert all("ERGONOMIA" in t["discipline"] for t in ergo_templates)

    target_tpl = ergo_templates[0]

    # Editar configuración visual de la plantilla (simulando editor visual frontend)
    update_resp = await client.put(
        f"/api/v1/report-templates/{target_tpl['id']}",
        json={
            "name": "Informe Ergonómico ROSA Personalizado",
            "template_config": {
                "palette": "aurora-teal-pro",
                "custom_header": "EMPRESA MINERA - EVALUACIÓN ERGONÓMICA 2026",
                "include_traffic_lights": True,
            },
        },
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["name"] == "Informe Ergonómico ROSA Personalizado"
    assert updated["template_config"]["palette"] == "aurora-teal-pro"
    assert updated["template_config"]["custom_header"] == "EMPRESA MINERA - EVALUACIÓN ERGONÓMICA 2026"


@pytest.mark.asyncio
async def test_pr16_sample_preview_watermark_and_download_protection(client: AsyncClient, session, seed_user, auth_headers):
    """2. Vista previa de muestra segura:
    - Genera PDF con marca de agua sin requerir orden pagada previa.
    - Bloquea la descarga de informe definitivo oficial sin pago."""
    org = Organization(name="Corporación Metalmecánica", tax_id="20555666777")
    session.add(org)
    await session.flush()
    session.add(OrganizationMembership(organization_id=org.id, user_id=seed_user.id, role_code="OWNER"))

    proj = Project(owner_user_id=seed_user.id, organization_id=org.id, name="Proyecto Metalmecánico", project_type="CUSTOM")
    session.add(proj)
    await session.flush()

    inst = Instrument(project_id=proj.id, organization_id=org.id, owner_user_id=seed_user.id, name="Test Preview", discipline="ERGONOMIA", status="ACTIVE")
    session.add(inst)
    await session.flush()

    opt = OptionSet(owner_user_id=seed_user.id, name="Likert", code="LKT")
    session.add(opt)
    await session.flush()
    session.add_all([
        OptionSetOption(option_set_id=opt.id, raw_code="1", label="1", numeric_value=1.0, sort_order=1),
        OptionSetOption(option_set_id=opt.id, raw_code="2", label="2", numeric_value=2.0, sort_order=2),
    ])
    await session.flush()

    ver = InstrumentVersion(instrument_id=inst.id, version_code="V1", status="AUTHORIZED", scoring_status="CONFIGURED")
    session.add(ver)
    await session.flush()

    q1 = Question(instrument_version_id=ver.id, option_set_id=opt.id, code="Q1", question_text="Q1", question_type="LIKERT", is_scored=True)
    session.add(q1)
    await session.flush()

    dim = Construct(instrument_version_id=ver.id, code="POSTURA", name="Postura", construct_type="DIMENSION")
    session.add(dim)
    await session.flush()
    session.add(ConstructItem(construct_id=dim.id, question_id=q1.id, weight=1.0))
    await session.flush()

    survey = Survey(project_id=proj.id, instrument_version_id=ver.id, created_by_user_id=seed_user.id, name="Survey Prev", survey_type="CUSTOM")
    session.add(survey)
    await session.flush()
    session.add(SurveyQuestion(survey_id=survey.id, question_id=q1.id, sort_order=1))
    await session.commit()

    study = await StudyService(session).create(proj.id, StudyCreate(survey_id=survey.id, name="Estudio Preview Watermark", study_type="CUSTOM", min_publishable_n=1))
    await StudyService(session).open(study.id)

    # Sesión y scoring
    resp_svc = ResponseService(session)
    sess1 = await resp_svc.create_session(study.id)
    await resp_svc.upsert_response(sess1.id, q1.id, ResponseUpsert(numeric_value=2.0, raw_code="2"))
    await resp_svc.complete_session(sess1.id, ResponseSessionCompleteRequest())
    await ScoringService(session).run(study.id)

    # 1. Solicitar vista previa de muestra (is_sample_preview=True)
    preview_resp = await client.post(
        f"/api/v1/studies/{study.id}/reports/preview",
        json={"is_sample_preview": True, "output_format": "PDF"},
        headers=auth_headers,
    )
    assert preview_resp.status_code == 201
    preview_data = preview_resp.json()
    assert preview_data["is_sample"] is True
    assert "VISTA PREVIA DE MUESTRA" in preview_data["watermark"]
    assert preview_data["pages"] >= 1

    # 2. Descargar PDF de vista previa (accesible con marca de agua)
    preview_pdf_resp = await client.get(f"/api/v1/reports/{preview_data['preview_id']}/preview.pdf", headers=auth_headers)
    assert preview_pdf_resp.status_code == 200
    assert preview_pdf_resp.headers["content-type"] == "application/pdf"
    assert preview_pdf_resp.content[:5] == b"%PDF-"

    # 3. Intentar descargar el informe definitivo oficial sin haber pagado debe ser RECHAZADO
    download_resp = await client.get(f"/api/v1/reports/{preview_data['preview_id']}/download", headers=auth_headers)
    assert download_resp.status_code == 409
    resp_err = download_resp.json()
    msg = resp_err.get("detail") or resp_err.get("message") or resp_err.get("error", {}).get("message", "")
    assert "No es posible descargar el informe definitivo oficial" in str(msg)


@pytest.mark.asyncio
async def test_pr16_definitive_report_emission_atomic_billing_and_audit(client: AsyncClient, session, seed_user, auth_headers):
    """3. Emisión definitiva del informe:
    - Exige orden pagada y no consumida.
    - Consume atómicamente la orden.
    - Genera hash criptográfico SHA-256 e historial inmutable."""
    org = Organization(name="Industrial Andina S.A.", tax_id="20444555666")
    session.add(org)
    await session.flush()
    session.add(OrganizationMembership(organization_id=org.id, user_id=seed_user.id, role_code="OWNER"))

    proj = Project(owner_user_id=seed_user.id, organization_id=org.id, name="Proyecto Andina", project_type="CUSTOM")
    session.add(proj)
    await session.flush()

    inst = Instrument(project_id=proj.id, organization_id=org.id, owner_user_id=seed_user.id, name="Instrumento Andina", discipline="PSICOSOCIAL", status="ACTIVE")
    session.add(inst)
    await session.flush()

    opt = OptionSet(owner_user_id=seed_user.id, name="Opt", code="OPT")
    session.add(opt)
    await session.flush()
    session.add_all([
        OptionSetOption(option_set_id=opt.id, raw_code="1", label="1", numeric_value=1.0, sort_order=1),
        OptionSetOption(option_set_id=opt.id, raw_code="2", label="2", numeric_value=2.0, sort_order=2),
    ])
    await session.flush()

    ver = InstrumentVersion(instrument_id=inst.id, version_code="V1", status="AUTHORIZED", scoring_status="CONFIGURED")
    session.add(ver)
    await session.flush()

    q1 = Question(instrument_version_id=ver.id, option_set_id=opt.id, code="Q1", question_text="Q1", question_type="LIKERT", is_scored=True)
    session.add(q1)
    await session.flush()

    dim = Construct(instrument_version_id=ver.id, code="ESTRES", name="Estrés", construct_type="DIMENSION")
    session.add(dim)
    await session.flush()
    session.add(ConstructItem(construct_id=dim.id, question_id=q1.id, weight=1.0))
    await session.flush()

    barem = Barem(instrument_version_id=ver.id, name="Baremo Andina", status="ACTIVE")
    session.add(barem)
    await session.flush()
    session.add_all([
        BaremBand(barem_id=barem.id, construct_id=dim.id, code="RIESGO_BAJO", classification_code="RIESGO_BAJO", label="Bajo", min_value=0, max_value=50, severity_order=1),
        BaremBand(barem_id=barem.id, construct_id=dim.id, code="RIESGO_ALTO", classification_code="RIESGO_ALTO", label="Alto", min_value=50, max_value=100, severity_order=2),
    ])
    await session.flush()

    survey = Survey(project_id=proj.id, instrument_version_id=ver.id, created_by_user_id=seed_user.id, name="Survey Andina", survey_type="CUSTOM")
    session.add(survey)
    await session.flush()
    session.add(SurveyQuestion(survey_id=survey.id, question_id=q1.id, sort_order=1))
    await session.commit()

    study = await StudyService(session).create(proj.id, StudyCreate(survey_id=survey.id, name="Campaña Andina 2026", study_type="CUSTOM", min_publishable_n=1))
    study.barem_id = barem.id
    await session.commit()
    await StudyService(session).open(study.id)

    resp_svc = ResponseService(session)
    sess1 = await resp_svc.create_session(study.id)
    await resp_svc.upsert_response(sess1.id, q1.id, ResponseUpsert(numeric_value=2.0, raw_code="2"))
    await resp_svc.complete_session(sess1.id, ResponseSessionCompleteRequest())
    await ScoringService(session).run(study.id)

    # Tarifa y Orden comercial pagada
    tariff = ReportTariff(
        method_code="CENSOPAS_CORTA",
        pricing_mode="FIXED",
        min_workers=1,
        max_workers=100,
        price=Decimal("400.00"),
        active=True,
        updated_by_user_id=seed_user.id,
    )
    session.add(tariff)
    await session.flush()

    order = ReportOrder(
        study_id=study.id,
        organization_id=org.id,
        tariff_id=tariff.id,
        requested_by_user_id=seed_user.id,
        method_code="CENSOPAS_CORTA",
        pricing_mode="FIXED",
        workers=15,
        tariff_min_workers=1,
        tariff_max_workers=100,
        headcount_source="ESTUDIO_DECLARADO",
        snapshot_data={},
        amount=Decimal("400.00"),
        currency="PEN",
        status="PAID",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    session.add(order)
    await session.commit()

    # 1. Emisión definitiva de informe DOCX
    emit_resp = await client.post(
        f"/api/v1/studies/{study.id}/reports",
        json={"billing_order_id": order.id, "output_format": "DOCX", "report_mode": "OFFICIAL"},
        headers=auth_headers,
    )
    assert emit_resp.status_code == 201
    report_data = emit_resp.json()
    assert report_data["status"] == "COMPLETED"
    assert report_data["data_hash"] is not None
    assert len(report_data["data_hash"]) == 64  # SHA-256
    assert report_data["billing_order_id"] == order.id

    # 2. Verificar que la orden pasó a CONSUMED
    await session.refresh(order)
    assert order.status == "CONSUMED"

    # 3. Descargar archivo oficial DOCX
    dl_resp = await client.get(f"/api/v1/reports/{report_data['id']}/download", headers=auth_headers)
    assert dl_resp.status_code == 200
    assert dl_resp.content[:4] == b"PK\x03\x04"  # Encabezado ZIP/DOCX

    # 4. Auditoría detallada del reporte
    audit_resp = await client.get(f"/api/v1/reports/{report_data['id']}/audit", headers=auth_headers)
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()
    assert audit_data["data_hash"] == report_data["data_hash"]
    assert audit_data["billing_order_id"] == order.id
    assert audit_data["billing_order_status"] == "CONSUMED"
    assert audit_data["integrity_verified"] is True
    assert audit_data["access_logs_count"] >= 1


@pytest.mark.asyncio
async def test_pr16_executive_dashboard_and_recommendations(client: AsyncClient, session, seed_user, auth_headers):
    """4. Dashboard ejecutivo con distribución de riesgo, semáforos y recomendaciones automáticas."""
    org = Organization(name="Minera Antamina Corp", tax_id="20333444555")
    session.add(org)
    await session.flush()
    session.add(OrganizationMembership(organization_id=org.id, user_id=seed_user.id, role_code="OWNER"))

    proj = Project(owner_user_id=seed_user.id, organization_id=org.id, name="Proyecto Ergonomía Mina", project_type="CUSTOM")
    session.add(proj)
    await session.flush()

    inst = Instrument(project_id=proj.id, organization_id=org.id, owner_user_id=seed_user.id, name="Evaluación Ergonomía Operativa", discipline="ERGONOMIA", status="ACTIVE")
    session.add(inst)
    await session.flush()

    opt = OptionSet(owner_user_id=seed_user.id, name="Likert 3", code="L3")
    session.add(opt)
    await session.flush()
    session.add_all([
        OptionSetOption(option_set_id=opt.id, raw_code="1", label="1", numeric_value=1.0, sort_order=1),
        OptionSetOption(option_set_id=opt.id, raw_code="2", label="2", numeric_value=2.0, sort_order=2),
        OptionSetOption(option_set_id=opt.id, raw_code="3", label="3", numeric_value=3.0, sort_order=3),
    ])
    await session.flush()

    ver = InstrumentVersion(instrument_id=inst.id, version_code="V1_ERGO", status="AUTHORIZED", scoring_status="CONFIGURED")
    session.add(ver)
    await session.flush()

    q1 = Question(instrument_version_id=ver.id, option_set_id=opt.id, code="POSTURA_CUELLO", question_text="Cuello", question_type="LIKERT", is_scored=True)
    session.add(q1)
    await session.flush()

    dim = Construct(instrument_version_id=ver.id, code="CUELLO_CARGA", name="Carga Cervical y Postural", construct_type="DIMENSION")
    session.add(dim)
    await session.flush()
    session.add(ConstructItem(construct_id=dim.id, question_id=q1.id, weight=1.0))
    await session.flush()

    barem = Barem(instrument_version_id=ver.id, name="Baremo Ergonómico", status="ACTIVE")
    session.add(barem)
    await session.flush()
    session.add_all([
        BaremBand(barem_id=barem.id, construct_id=dim.id, code="RIESGO_ALTO", classification_code="RIESGO_ALTO", label="Riesgo Alto", min_value=50, max_value=100, severity_order=1),
        BaremBand(barem_id=barem.id, construct_id=dim.id, code="RIESGO_BAJO", classification_code="RIESGO_BAJO", label="Riesgo Bajo", min_value=0, max_value=50, severity_order=2),
    ])
    await session.flush()

    survey = Survey(project_id=proj.id, instrument_version_id=ver.id, created_by_user_id=seed_user.id, name="Survey Ergo Mina", survey_type="CUSTOM")
    session.add(survey)
    await session.flush()
    session.add(SurveyQuestion(survey_id=survey.id, question_id=q1.id, sort_order=1))
    await session.commit()

    study = await StudyService(session).create(proj.id, StudyCreate(survey_id=survey.id, name="Estudio Ergo 2026", study_type="CUSTOM", min_publishable_n=1))
    study.barem_id = barem.id
    await session.commit()
    await StudyService(session).open(study.id)

    resp_svc = ResponseService(session)
    sess1 = await resp_svc.create_session(study.id)
    await resp_svc.upsert_response(sess1.id, q1.id, ResponseUpsert(numeric_value=3.0, raw_code="3"))
    await resp_svc.complete_session(sess1.id, ResponseSessionCompleteRequest())
    await ScoringService(session).run(study.id)

    # Consultar dashboard ejecutivo
    dash_resp = await client.get(f"/api/v1/studies/{study.id}/reports/executive-dashboard", headers=auth_headers)
    assert dash_resp.status_code == 200
    dashboard = dash_resp.json()
    assert dashboard["study_id"] == study.id
    assert dashboard["discipline"] == "ERGONOMIA"
    assert dashboard["participation"]["valid_count"] == 1
    assert dashboard["risk_distribution"]["high_risk_count"] == 1

    rankings = dashboard["construct_rankings"]
    assert len(rankings) >= 1
    target_rank = rankings[0]
    assert target_rank["construct_code"] == "CUELLO_CARGA"
    assert target_rank["traffic_light"] == "RED"
    assert "Intervención inmediata" in target_rank["recommendation"]
    assert "micro-pausas" in target_rank["recommendation"]


@pytest.mark.asyncio
async def test_pr16_organization_reports_history_with_filters(client: AsyncClient, session, seed_user, auth_headers):
    """5. Historial empresarial de informes con filtros por disciplina y campaña."""
    org = Organization(name="Holding Multidisciplinario", tax_id="20123456789")
    session.add(org)
    await session.flush()
    session.add(OrganizationMembership(organization_id=org.id, user_id=seed_user.id, role_code="OWNER"))

    proj = Project(owner_user_id=seed_user.id, organization_id=org.id, name="Proyecto Holding", project_type="CUSTOM")
    session.add(proj)
    await session.flush()

    inst = Instrument(project_id=proj.id, organization_id=org.id, owner_user_id=seed_user.id, name="Instrumento Holding", discipline="CLIMA", status="ACTIVE")
    session.add(inst)
    await session.flush()

    opt = OptionSet(owner_user_id=seed_user.id, name="Opt", code="OPT")
    session.add(opt)
    await session.flush()
    session.add_all([
        OptionSetOption(option_set_id=opt.id, raw_code="1", label="1", numeric_value=1.0, sort_order=1),
        OptionSetOption(option_set_id=opt.id, raw_code="2", label="2", numeric_value=2.0, sort_order=2),
    ])
    await session.flush()

    ver = InstrumentVersion(instrument_id=inst.id, version_code="V1_CLIMA", status="AUTHORIZED", scoring_status="CONFIGURED")
    session.add(ver)
    await session.flush()

    q1 = Question(instrument_version_id=ver.id, option_set_id=opt.id, code="CLIMA_1", question_text="Liderazgo", question_type="LIKERT", is_scored=True)
    session.add(q1)
    await session.flush()

    dim = Construct(instrument_version_id=ver.id, code="LIDERAZGO", name="Liderazgo", construct_type="DIMENSION")
    session.add(dim)
    await session.flush()
    session.add(ConstructItem(construct_id=dim.id, question_id=q1.id, weight=1.0))
    await session.flush()

    survey = Survey(project_id=proj.id, instrument_version_id=ver.id, created_by_user_id=seed_user.id, name="Survey Clima", survey_type="CUSTOM")
    session.add(survey)
    await session.flush()
    session.add(SurveyQuestion(survey_id=survey.id, question_id=q1.id, sort_order=1))
    await session.commit()

    study = await StudyService(session).create(proj.id, StudyCreate(survey_id=survey.id, name="Campaña Clima 2026", study_type="CUSTOM", min_publishable_n=1))
    await StudyService(session).open(study.id)

    resp_svc = ResponseService(session)
    sess1 = await resp_svc.create_session(study.id)
    await resp_svc.upsert_response(sess1.id, q1.id, ResponseUpsert(numeric_value=2.0, raw_code="2"))
    await resp_svc.complete_session(sess1.id, ResponseSessionCompleteRequest())
    await ScoringService(session).run(study.id)

    # Generar vista previa de muestra
    await client.post(
        f"/api/v1/studies/{study.id}/reports/preview",
        json={"is_sample_preview": True, "output_format": "PDF"},
        headers=auth_headers,
    )

    # Consultar historial de la organización
    hist_resp = await client.get(f"/api/v1/organizations/{org.id}/reports/history", headers=auth_headers)
    assert hist_resp.status_code == 200
    history = hist_resp.json()
    assert len(history) >= 1

    item = history[0]
    assert item["study_id"] == study.id
    assert item["study_name"] == "Campaña Clima 2026"
    assert item["is_sample_preview"] is True

    # Filtrar por disciplina CLIMA
    clima_hist_resp = await client.get(f"/api/v1/organizations/{org.id}/reports/history?discipline=CLIMA", headers=auth_headers)
    assert clima_hist_resp.status_code == 200
    assert len(clima_hist_resp.json()) >= 1
