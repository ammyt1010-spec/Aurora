"""Pruebas del Flujo Empresarial Integral de AURORA Professional (PR #15).

Cubre los 8 pilares del ciclo de vida de evaluación empresarial:
1. Selección de metodología e instrumento autorizado (rechazo de borradores/no configurados).
2. Configuración de estructura organizativa (sedes, áreas, grupos) y congelación en snapshot.
3. Gestión del ciclo de vida de invitaciones (emisión, consulta, revocación y control de un solo uso).
4. Captura de respuestas con token y vinculación a versión congelada.
5. Guardado parcial, seguimiento de progreso y congelación por sesión.
6. Cierre del estudio y bloqueo global de nuevas respuestas y asignaciones.
7. Scoring psicométrico con desglose por unidades organizacionales.
8. Anonimato estricto (supresión bajo umbral N) y comparabilidad longitudinal.
"""

from datetime import UTC, datetime, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import ConflictError, ValidationDomainError, PublicResourceUnavailableError
from app.core.security import create_access_token
from app.models.construct import Construct, ConstructItem
from app.models.instrument import Instrument, InstrumentVersion
from app.models.option_set import OptionSet, OptionSetOption
from app.models.project import Project
from app.models.question import Question
from app.models.response import ResponseSession
from app.models.scoring import ScoringRule
from app.models.study import Study, StudySnapshot, StudyUnit, StudyUnitType
from app.models.survey import Survey, SurveyQuestion, SurveySection
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.responses import ResponseUpsert, ResponseSessionCompleteRequest
from app.schemas.studies import ResponseSessionUnitsReplace, StudyCreate, StudyUnitCreate, StudyUnitTypeCreate
from app.services.invitation_service import InvitationService
from app.services.public_survey_service import PublicSurveyService
from app.services.response_service import ResponseService
from app.services.scoring_orchestrator import run_canonical_scoring
from app.services.scoring_service import ScoringService
from app.services.study_service import StudyService
from app.services.survey_service import SurveyService


@pytest.fixture
def auth_headers(seed_user):
    token = create_access_token(seed_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_enterprise_campaign_full_workflow(client: AsyncClient, session, seed_project, seed_user, auth_headers):
    # -------------------------------------------------------------------------
    # 1. Metodología e Instrumento Autorizado
    # -------------------------------------------------------------------------
    instrument = Instrument(
        project_id=seed_project.id,
        owner_user_id=seed_user.id,
        name="Evaluación de Clima y Ergonomía",
        discipline="ERGONOMIA",
        status="ACTIVE",
    )
    session.add(instrument)
    await session.flush()

    # Opción Likert estándar (1: Bajo, 2: Medio, 3: Alto)
    option_set = OptionSet(owner_user_id=seed_user.id, name="Likert 3", code="LIKERT_3")
    session.add(option_set)
    await session.flush()
    session.add_all([
        OptionSetOption(option_set_id=option_set.id, raw_code="1", label="Bajo", numeric_value=1.0, sort_order=1, is_active=True),
        OptionSetOption(option_set_id=option_set.id, raw_code="2", label="Medio", numeric_value=2.0, sort_order=2, is_active=True),
        OptionSetOption(option_set_id=option_set.id, raw_code="3", label="Alto", numeric_value=3.0, sort_order=3, is_active=True),
    ])
    await session.flush()

    # Versión en borrador (DRAFT)
    draft_version = InstrumentVersion(
        instrument_id=instrument.id,
        version_code="V1_DRAFT",
        status="DRAFT",
        scoring_status="NOT_CONFIGURED",
    )
    session.add(draft_version)
    await session.flush()

    # Preguntas
    q1 = Question(
        instrument_version_id=draft_version.id,
        option_set_id=option_set.id,
        code="ERGO_01",
        question_text="¿La postura de trabajo es cómoda?",
        question_type="LIKERT",
        is_scored=True,
    )
    q2 = Question(
        instrument_version_id=draft_version.id,
        option_set_id=option_set.id,
        code="ERGO_02",
        question_text="¿La iluminación del puesto es adecuada?",
        question_type="LIKERT",
        is_scored=True,
    )
    session.add_all([q1, q2])
    await session.flush()

    # Constructo
    dimension = Construct(
        instrument_version_id=draft_version.id,
        code="CONDICIONES_FISICAS",
        name="Condiciones Físicas de Trabajo",
        construct_type="DIMENSION",
    )
    session.add(dimension)
    await session.flush()

    session.add_all([
        ConstructItem(construct_id=dimension.id, question_id=q1.id, weight=1.0, scoring_direction="DIRECT"),
        ConstructItem(construct_id=dimension.id, question_id=q2.id, weight=1.0, scoring_direction="DIRECT"),
    ])
    await session.flush()

    # Survey
    survey_service = SurveyService(session)
    survey = Survey(
        project_id=seed_project.id,
        instrument_version_id=draft_version.id,
        created_by_user_id=seed_user.id,
        name="Cuestionario de Condiciones Físicas",
        survey_type="CUSTOM",
    )
    session.add(survey)
    await session.flush()
    session.add_all([
        SurveyQuestion(survey_id=survey.id, question_id=q1.id, sort_order=1),
        SurveyQuestion(survey_id=survey.id, question_id=q2.id, sort_order=2),
    ])
    await session.commit()

    study_service = StudyService(session)
    study = await study_service.create(
        seed_project.id,
        StudyCreate(
            survey_id=survey.id,
            name="Campaña Ergonomía 2026",
            study_type="CUSTOM",
            min_publishable_n=5,
            requires_invitation=True,
            settings={"is_enterprise_evaluation": True},
        ),
    )

    # 1.A. Intento de abrir con versión no autorizada debe fallar
    with pytest.raises(ValidationDomainError, match="no está en estado AUTHORIZED o ACTIVE"):
        await study_service.open(study.id)

    # Autorizamos y configuramos la versión
    draft_version.status = "AUTHORIZED"
    draft_version.scoring_status = "CONFIGURED"
    await session.commit()

    # -------------------------------------------------------------------------
    # 2. Estructura Organizativa (Sedes, Áreas)
    # -------------------------------------------------------------------------
    unit_type_sede = await study_service.create_unit_type(
        study.id,
        StudyUnitTypeCreate(code="SEDE", name="Sede Operativa", sort_order=1),
    )
    unit_type_area = await study_service.create_unit_type(
        study.id,
        StudyUnitTypeCreate(code="AREA", name="Área Funcional", sort_order=2),
    )

    sede_lima = await study_service.create_unit(
        unit_type_sede.id,
        StudyUnitCreate(code="SEDE_LIMA", name="Planta Principal Lima"),
    )
    area_prod = await study_service.create_unit(
        unit_type_area.id,
        StudyUnitCreate(code="AREA_PROD", name="Operaciones y Producción"),
    )
    area_admin = await study_service.create_unit(
        unit_type_area.id,
        StudyUnitCreate(code="AREA_ADMIN", name="Administración y Finanzas"),
    )

    # Abrir el estudio: se congela la estructura y versión en snapshot
    opened_study = await study_service.open(study.id)
    assert opened_study.status == "OPEN"

    # Verificar que el snapshot STUDY_OPEN contiene la estructura organizativa
    snapshot = (
        await session.execute(
            select(StudySnapshot).where(
                StudySnapshot.study_id == study.id,
                StudySnapshot.snapshot_type == "STUDY_OPEN",
            )
        )
    ).scalar_one()
    assert "organizational_structure" in snapshot.snapshot_data
    org_struct = snapshot.snapshot_data["organizational_structure"]
    assert len(org_struct["unit_types"]) == 2
    assert len(org_struct["units"]) == 3

    # 2.B. Intentar agregar unidades después de abierto debe ser rechazado
    with pytest.raises(ConflictError, match="deben configurarse antes de abrir"):
        await study_service.create_unit(
            unit_type_sede.id,
            StudyUnitCreate(code="SEDE_SUR", name="Sede Sur"),
        )

    # -------------------------------------------------------------------------
    # 3. Gestión y Ciclo de Vida de Invitaciones
    # -------------------------------------------------------------------------
    invitation_service = InvitationService(session)
    tokens = await invitation_service.issue(study.id, count=4)
    assert len(tokens) == 4

    summary = await invitation_service.summary(study.id, include_revoked=True)
    assert summary["total"] == 4
    assert summary["pending"] == 4
    assert summary["consumed"] == 0
    assert summary["revoked"] == 0

    invitations_list = await invitation_service.list_invitations(study.id)
    assert len(invitations_list) == 4

    # Revocar la 4ta invitación
    revoked = await invitation_service.revoke(study.id, invitations_list[3].id, reason="Cancelación de puesto")
    assert revoked.status == "REVOKED"
    assert revoked.metadata_["revocation_reason"] == "Cancelación de puesto"

    summary_after_revoke = await invitation_service.summary(study.id, include_revoked=True)
    assert summary_after_revoke["pending"] == 3
    assert summary_after_revoke["revoked"] == 1

    # 3.B. Canje de token revocado debe fallar
    public_service = PublicSurveyService(session)
    revoked_token = tokens[3]
    with pytest.raises(PublicResourceUnavailableError):
        await public_service.create_session_for_public_study(study.public_id, invitation_token=revoked_token)

    # -------------------------------------------------------------------------
    # 4. Captura de Respuestas y Control de Un Solo Uso
    # -------------------------------------------------------------------------
    valid_token_1 = tokens[0]
    session_1 = await public_service.create_session_for_public_study(
        study.public_id, invitation_token=valid_token_1
    )
    assert session_1.status == "STARTED"

    # Intentar reutilizar el mismo token debe ser rechazado
    with pytest.raises(PublicResourceUnavailableError):
        await public_service.create_session_for_public_study(
            study.public_id, invitation_token=valid_token_1
        )

    # Asignar unidades organizacionales a la sesión 1
    response_service = ResponseService(session)
    await response_service.replace_session_units(
        session_1.id,
        ResponseSessionUnitsReplace(unit_ids=[sede_lima.id, area_prod.id]),
    )

    # -------------------------------------------------------------------------
    # 5. Guardado Parcial, Progreso y Congelación de Sesión
    # -------------------------------------------------------------------------
    # Responder solo pregunta 1
    await response_service.upsert_response(
        session_1.id,
        q1.id,
        ResponseUpsert(numeric_value=3.0, raw_code="3"),
    )

    progress_partial = await response_service.get_session_progress(session_1.id)
    assert progress_partial.status == "IN_PROGRESS"
    assert progress_partial.answered_questions == 1
    assert progress_partial.total_questions == 2
    assert progress_partial.completion_pct == 50.0
    assert progress_partial.can_resume is True

    # Consultar respuestas guardadas
    saved_answers = await response_service.list_session_responses(session_1.id)
    assert len(saved_answers) == 1
    assert saved_answers[0].question_id == q1.id

    # Responder pregunta 2 y completar sesión
    await response_service.upsert_response(
        session_1.id,
        q2.id,
        ResponseUpsert(numeric_value=2.0, raw_code="2"),
    )
    completed_session_1 = await response_service.complete_session(session_1.id, ResponseSessionCompleteRequest())
    assert completed_session_1.status == "COMPLETED"
    assert completed_session_1.validation_status == "VALID"

    # 5.B. Sesión completada no admite más respuestas ni cambios de unidad
    with pytest.raises(ConflictError, match="La sesión ya fue completada"):
        await response_service.upsert_response(
            session_1.id, q1.id, ResponseUpsert(numeric_value=1.0, raw_code="1")
        )
    with pytest.raises(ConflictError, match="La sesión ya fue completada"):
        await response_service.replace_session_units(
            session_1.id, ResponseSessionUnitsReplace(unit_ids=[sede_lima.id, area_admin.id])
        )

    # Crear y completar sesión 2 con token 2 en Sede Lima y Área Producción
    valid_token_2 = tokens[1]
    session_2 = await public_service.create_session_for_public_study(
        study.public_id, invitation_token=valid_token_2
    )
    await response_service.replace_session_units(
        session_2.id,
        ResponseSessionUnitsReplace(unit_ids=[sede_lima.id, area_prod.id]),
    )
    await response_service.upsert_response(session_2.id, q1.id, ResponseUpsert(numeric_value=3.0, raw_code="3"))
    await response_service.upsert_response(session_2.id, q2.id, ResponseUpsert(numeric_value=3.0, raw_code="3"))
    await response_service.complete_session(session_2.id, ResponseSessionCompleteRequest())

    # -------------------------------------------------------------------------
    # 6. Cierre del Estudio y Bloqueo Global
    # -------------------------------------------------------------------------
    closed_study = await study_service.close(study.id)
    assert closed_study.status == "CLOSED"

    # Intentar responder en una nueva sesión o cambiar unidades en estudio cerrado
    with pytest.raises(ConflictError, match="El estudio no admite nuevas respuestas"):
        # Simulamos sesión no completada
        unclosed_session = ResponseSession(study_id=study.id, status="STARTED")
        session.add(unclosed_session)
        await session.commit()
        await response_service.upsert_response(
            unclosed_session.id, q1.id, ResponseUpsert(numeric_value=2.0, raw_code="2")
        )

    # -------------------------------------------------------------------------
    # 7. Procesamiento Psicométrico y Agregación por Unidades
    # -------------------------------------------------------------------------
    run, score_summary = await run_canonical_scoring(session, study.id)
    assert run.status == "COMPLETED"
    assert score_summary.constructs_scored >= 1
    assert score_summary.sessions_processed == 2

    # -------------------------------------------------------------------------
    # 8. Anonimato y Comparabilidad Longitudinal
    # -------------------------------------------------------------------------
    # n=2 < min_publishable_n=5 => Resultados agregados deben estar suprimidos
    scoring_service = ScoringService(session)
    overview = await scoring_service.get_overview(study.id)
    assert overview.n_completed == 2
    assert overview.min_publishable_n == 5
    for result in overview.results:
        assert result.suppressed is True
        assert result.mean_score is None

    # Trazabilidad Longitudinal en el Proyecto
    from app.services.analysis_service import AnalysisService
    analysis_service = AnalysisService(session)
    longitudinal = await analysis_service.get_longitudinal_comparison(seed_project.id)
    assert longitudinal.project_id == seed_project.id
    assert longitudinal.total_studies_analyzed >= 1
    assert len(longitudinal.constructs) >= 1
    construct_trend = longitudinal.constructs[0]
    assert construct_trend.construct_code == "CONDICIONES_FISICAS"
    assert len(construct_trend.points) >= 1
    assert construct_trend.points[0].suppressed is True


@pytest.mark.asyncio
async def test_enterprise_campaign_api_endpoints(client: AsyncClient, session, seed_project, seed_user, auth_headers):
    # Setup study and invitation
    survey = Survey(
        project_id=seed_project.id,
        created_by_user_id=seed_user.id,
        name="Encuesta API",
        survey_type="CUSTOM",
    )
    session.add(survey)
    await session.commit()

    study = await StudyService(session).create(
        seed_project.id,
        StudyCreate(
            survey_id=survey.id,
            name="Estudio API Test",
            study_type="CUSTOM",
            min_publishable_n=3,
            requires_invitation=True,
        ),
    )
    await StudyService(session).open(study.id)

    # 1. Issue invitations
    issue_resp = await client.post(
        f"/api/v1/studies/{study.id}/invitations",
        json={"count": 2},
        headers=auth_headers,
    )
    assert issue_resp.status_code == 201, issue_resp.text
    tokens = issue_resp.json()["tokens"]
    assert len(tokens) == 2

    # 2. List invitations via API
    list_resp = await client.get(f"/api/v1/studies/{study.id}/invitations/list", headers=auth_headers)
    assert list_resp.status_code == 200, list_resp.text
    invitations = list_resp.json()
    assert len(invitations) == 2
    inv_id = invitations[0]["id"]

    # 3. Revoke invitation via API
    revoke_resp = await client.post(
        f"/api/v1/studies/{study.id}/invitations/{inv_id}/revoke?reason=Error%20operativo",
        headers=auth_headers,
    )
    assert revoke_resp.status_code == 200, revoke_resp.text
    assert revoke_resp.json()["status"] == "REVOKED"

    # 4. Create session and verify progress and responses endpoints
    session_resp = await client.post(
        f"/api/v1/studies/{study.id}/response-sessions",
        headers=auth_headers,
    )
    assert session_resp.status_code == 201, session_resp.text
    sess_id = session_resp.json()["id"]

    sess_get = await client.get(f"/api/v1/response-sessions/{sess_id}", headers=auth_headers)
    assert sess_get.status_code == 200
    assert sess_get.json()["id"] == sess_id

    progress_resp = await client.get(f"/api/v1/response-sessions/{sess_id}/progress", headers=auth_headers)
    assert progress_resp.status_code == 200
    assert progress_resp.json()["response_session_id"] == sess_id
    assert progress_resp.json()["is_completed"] is False

    responses_list_resp = await client.get(f"/api/v1/response-sessions/{sess_id}/responses", headers=auth_headers)
    assert responses_list_resp.status_code == 200
    assert isinstance(responses_list_resp.json(), list)

    # 5. Longitudinal analytics via API
    long_resp = await client.get(
        f"/api/v1/projects/{seed_project.id}/analytics/longitudinal",
        headers=auth_headers,
    )
    assert long_resp.status_code == 200, long_resp.text
    data = long_resp.json()
    assert data["project_id"] == seed_project.id
    assert "constructs" in data
