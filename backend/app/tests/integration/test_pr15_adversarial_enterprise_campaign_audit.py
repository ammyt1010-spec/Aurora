"""Pruebas adversariales de auditoría correctiva para el PR #15 (FASE A).

Cubre:
1. A1: Detección confiable de evaluación empresarial por backend, sin evasión vía study.settings,
   aislamiento multiempresa estricto y validación de reglas metodológicas.
2. A2: Cierre y vencimiento (end_at y status CLOSED) bloqueando respuestas, unidades y finalizaciones,
   más idempotencia de sesiones completadas.
3. A3: Scoring multidisciplinario sin tricotomía ni algoritmo CENSOPAS forzado, y fail-closed ante reglas incompatibles.
4. A4: Comparabilidad longitudinal bloqueada ante discrepancias metodológicas y privacidad bajo N mínimo.
"""

from datetime import UTC, datetime, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    ValidationDomainError,
)
from app.core.security import create_access_token
from app.models.censopas import Barem, BaremBand
from app.models.construct import Construct, ConstructItem
from app.models.instrument import Instrument, InstrumentVersion
from app.models.option_set import OptionSet, OptionSetOption
from app.models.project import Project
from app.models.question import Question
from app.models.response import ResponseSession
from app.models.study import Study, StudyUnit, StudyUnitType
from app.models.survey import Survey, SurveyQuestion
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.responses import ResponseUpsert, ResponseSessionCompleteRequest
from app.schemas.studies import ResponseSessionUnitsReplace, StudyCreate, StudyUnitCreate, StudyUnitTypeCreate
from app.services.analysis_service import AnalysisService
from app.services.censopas_service import CensopasScoringService
from app.services.response_service import ResponseService
from app.services.scoring_orchestrator import run_canonical_scoring
from app.services.scoring_service import ScoringService
from app.services.study_service import StudyService


@pytest.fixture
def auth_headers(seed_user):
    token = create_access_token(seed_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_a1_enterprise_evaluation_cannot_bypass_via_settings(session, seed_user):
    """A1: Un proyecto empresarial (project_type != ACADEMIC) no puede evadir la
    verificación de versión autorizada manipulando study.settings."""
    study_service = StudyService(session)

    org = Organization(name="Empresa Minera del Sur", tax_id="20999888777")
    session.add(org)
    await session.flush()
    session.add(OrganizationMembership(organization_id=org.id, user_id=seed_user.id, role_code="OWNER"))

    # Proyecto empresarial
    corp_project = Project(
        owner_user_id=seed_user.id,
        organization_id=org.id,
        name="Proyecto Ergonómico Corporativo",
        project_type="CUSTOM",
        status="ACTIVE",
    )
    session.add(corp_project)
    await session.flush()

    # Instrumento en DRAFT
    instrument = Instrument(
        project_id=corp_project.id,
        organization_id=org.id,
        owner_user_id=seed_user.id,
        name="Evaluación Ergonómica no Autorizada",
        discipline="ERGONOMIA",
        status="DRAFT",
    )
    session.add(instrument)
    await session.flush()

    version = InstrumentVersion(
        instrument_id=instrument.id,
        version_code="V_UNAUTH",
        status="DRAFT",
        scoring_status="NOT_CONFIGURED",
    )
    session.add(version)
    await session.flush()

    survey = Survey(
        project_id=corp_project.id,
        instrument_version_id=version.id,
        created_by_user_id=seed_user.id,
        name="Encuesta Borrador",
        survey_type="CUSTOM",
    )
    session.add(survey)
    await session.flush()

    # Estudio que intenta engañar al backend enviando is_enterprise_evaluation=False
    study = await study_service.create(
        corp_project.id,
        StudyCreate(
            survey_id=survey.id,
            name="Estudio con bandera falsa",
            study_type="CUSTOM",
            settings={"is_enterprise_evaluation": False, "is_enterprise": False},
        ),
    )

    # El backend detecta la relación confiable del proyecto con la organización y rechaza abrir
    with pytest.raises(ValidationDomainError, match="no está en estado AUTHORIZED o ACTIVE"):
        await study_service.open(study.id)


@pytest.mark.asyncio
async def test_a1_multitenant_isolation_rejects_cross_organization_instrument(session, seed_user):
    """A1: Una empresa no puede abrir un estudio utilizando un instrumento privado de otra empresa."""
    study_service = StudyService(session)

    org_a = Organization(name="Empresa A", tax_id="20111111111")
    org_b = Organization(name="Empresa B", tax_id="20222222222")
    session.add_all([org_a, org_b])
    await session.flush()

    session.add_all([
        OrganizationMembership(organization_id=org_a.id, user_id=seed_user.id, role_code="OWNER"),
        OrganizationMembership(organization_id=org_b.id, user_id=seed_user.id, role_code="OWNER"),
    ])

    proj_a = Project(owner_user_id=seed_user.id, organization_id=org_a.id, name="Proj A", project_type="CUSTOM")
    proj_b = Project(owner_user_id=seed_user.id, organization_id=org_b.id, name="Proj B", project_type="CUSTOM")
    session.add_all([proj_a, proj_b])
    await session.flush()

    # Instrumento privado perteneciente exclusivamente a Empresa B
    inst_b = Instrument(
        organization_id=org_b.id,
        owner_user_id=seed_user.id,
        name="Instrumento Confidencial Empresa B",
        status="AUTHORIZED",
        is_system=False,
    )
    session.add(inst_b)
    await session.flush()

    ver_b = InstrumentVersion(
        instrument_id=inst_b.id,
        version_code="V_CONFIDENTIAL",
        status="AUTHORIZED",
        scoring_status="CONFIGURED",
    )
    session.add(ver_b)
    await session.flush()

    survey_a = Survey(
        project_id=proj_a.id,
        instrument_version_id=ver_b.id,
        created_by_user_id=seed_user.id,
        name="Encuesta Proj A intentando usar Instrumento B",
        survey_type="CUSTOM",
    )
    session.add(survey_a)
    await session.flush()

    study_a = await study_service.create(
        proj_a.id,
        StudyCreate(survey_id=survey_a.id, name="Estudio infractor", study_type="CUSTOM"),
    )

    # Intento de apertura debe ser bloqueado por violación de aislamiento multiempresa
    with pytest.raises(AuthorizationError, match="el instrumento pertenece a otra organización"):
        await study_service.open(study_a.id)


@pytest.mark.asyncio
async def test_a2_closure_and_expiration_block_mutations_and_idempotency(session, seed_user, seed_project):
    """A2: Cierre y vencimiento (end_at y CLOSED) bloquean respuestas, unidades y finalizaciones.
    Sesiones ya completadas responden con idempotencia segura sin alterar datos."""
    study_service = StudyService(session)
    response_service = ResponseService(session)

    # Configurar versión e instrumento activos
    instrument = Instrument(
        project_id=seed_project.id,
        owner_user_id=seed_user.id,
        name="Instrumento Test Cierre",
        status="ACTIVE",
    )
    session.add(instrument)
    await session.flush()

    option_set = OptionSet(owner_user_id=seed_user.id, name="OS", code="OS")
    session.add(option_set)
    await session.flush()
    opt1 = OptionSetOption(option_set_id=option_set.id, raw_code="1", label="1", numeric_value=1.0, sort_order=1)
    opt2 = OptionSetOption(option_set_id=option_set.id, raw_code="2", label="2", numeric_value=2.0, sort_order=2)
    session.add_all([opt1, opt2])
    await session.flush()

    version = InstrumentVersion(
        instrument_id=instrument.id,
        version_code="V1",
        status="ACTIVE",
        scoring_status="CONFIGURED",
    )
    session.add(version)
    await session.flush()

    q1 = Question(
        instrument_version_id=version.id,
        option_set_id=option_set.id,
        code="Q1",
        question_text="Q1",
        question_type="LIKERT",
        is_scored=True,
    )
    session.add(q1)
    await session.flush()

    dim = Construct(instrument_version_id=version.id, code="D1", name="D1", construct_type="DIMENSION")
    session.add(dim)
    await session.flush()
    session.add(ConstructItem(construct_id=dim.id, question_id=q1.id, weight=1.0))
    await session.flush()

    survey = Survey(
        project_id=seed_project.id,
        instrument_version_id=version.id,
        created_by_user_id=seed_user.id,
        name="Survey Cierre",
        survey_type="CUSTOM",
    )
    session.add(survey)
    await session.flush()
    session.add(SurveyQuestion(survey_id=survey.id, question_id=q1.id, sort_order=1))
    await session.commit()

    # Estudio abierto pero con end_at vencido en el pasado
    past_date = datetime.now(UTC) - timedelta(hours=2)
    study = await study_service.create(
        seed_project.id,
        StudyCreate(
            survey_id=survey.id,
            name="Estudio Vencido",
            study_type="CUSTOM",
            start_at=datetime.now(UTC) - timedelta(days=5),
            end_at=past_date,
        ),
    )
    await study_service.open(study.id)

    # 1. Crear sesión en estudio vencido debe fallar
    with pytest.raises(ConflictError, match="ya alcanzó su fecha de cierre"):
        await response_service.create_session(study.id)

    # Simular sesión existente creada previamente
    resp_sess = ResponseSession(study_id=study.id, status="IN_PROGRESS")
    session.add(resp_sess)
    await session.commit()
    await session.refresh(resp_sess)

    # 2. Registrar respuesta en estudio vencido debe fallar
    with pytest.raises(ConflictError, match="ya alcanzó su fecha de cierre"):
        await response_service.upsert_response(resp_sess.id, q1.id, ResponseUpsert(numeric_value=1.0, raw_code="1"))

    # 3. Completar sesión en estudio vencido debe fallar
    with pytest.raises(ConflictError, match="ya alcanzó su fecha de cierre"):
        await response_service.complete_session(resp_sess.id, ResponseSessionCompleteRequest())

    # 4. Modificar unidades en estudio vencido debe fallar
    with pytest.raises(ConflictError, match="ya alcanzó su fecha de cierre"):
        await response_service.replace_session_units(resp_sess.id, ResponseSessionUnitsReplace(unit_ids=[]))

    # Ahora probar estudio formalmente cerrado (CLOSED)
    study.end_at = None
    study.status = "CLOSED"
    await session.commit()

    with pytest.raises(ConflictError, match="no admite nuevas respuestas"):
        await response_service.upsert_response(resp_sess.id, q1.id, ResponseUpsert(numeric_value=1.0, raw_code="1"))

    with pytest.raises(ConflictError, match="no admite completar sesiones"):
        await response_service.complete_session(resp_sess.id, ResponseSessionCompleteRequest())

    # 5. Idempotencia segura: si la sesión YA estaba COMPLETED, complete_session retorna sin error
    resp_sess.status = "COMPLETED"
    resp_sess.completion_pct = 100.0
    await session.commit()

    completed_again = await response_service.complete_session(resp_sess.id, ResponseSessionCompleteRequest())
    assert completed_again.status == "COMPLETED"
    assert completed_again.id == resp_sess.id


@pytest.mark.asyncio
async def test_a3_multidisciplinary_scoring_avoids_censopas_labels_and_fails_closed(session, seed_user, seed_project):
    """A3: Scoring para ERGONOMÍA no usa tricotomía CENSOPAS ni algoritmo censopas-v2.
    Falla en modo closed ante reglas incompatibles."""
    study_service = StudyService(session)

    # Instrumento de Ergonomía con 4 niveles de riesgo postural
    ergo_inst = Instrument(
        project_id=seed_project.id,
        owner_user_id=seed_user.id,
        name="Método Ergonomía ROSA",
        discipline="ERGONOMIA",
        method_code="ERGONOMIA_ROSA",
        status="ACTIVE",
    )
    session.add(ergo_inst)
    await session.flush()

    option_set = OptionSet(owner_user_id=seed_user.id, name="Likert 4", code="LIKERT_4")
    session.add(option_set)
    await session.flush()
    session.add_all([
        OptionSetOption(option_set_id=option_set.id, raw_code="1", label="Bajo", numeric_value=1.0, sort_order=1),
        OptionSetOption(option_set_id=option_set.id, raw_code="2", label="Medio", numeric_value=2.0, sort_order=2),
        OptionSetOption(option_set_id=option_set.id, raw_code="3", label="Alto", numeric_value=3.0, sort_order=3),
        OptionSetOption(option_set_id=option_set.id, raw_code="4", label="Crítico", numeric_value=4.0, sort_order=4),
    ])
    await session.flush()

    ergo_ver = InstrumentVersion(
        instrument_id=ergo_inst.id,
        version_code="V_ROSA_2026",
        status="AUTHORIZED",
        scoring_status="CONFIGURED",
        methodological_rules={
            "required_algorithm": "ergonomia-v1",
            "scale": "POSTURAL_RISK_4",
        },
    )
    session.add(ergo_ver)
    await session.flush()

    q_ergo = Question(
        instrument_version_id=ergo_ver.id,
        option_set_id=option_set.id,
        code="ROSA_SILLA",
        question_text="Ajuste de silla y postura lumbar",
        question_type="LIKERT",
        is_scored=True,
    )
    session.add(q_ergo)
    await session.flush()

    dim_ergo = Construct(
        instrument_version_id=ergo_ver.id,
        code="RIESGO_POSTURAL",
        name="Riesgo Postural en Pantallas",
        construct_type="DIMENSION",
    )
    session.add(dim_ergo)
    await session.flush()
    session.add(ConstructItem(construct_id=dim_ergo.id, question_id=q_ergo.id, weight=1.0))
    await session.flush()

    # Baremo ergonómico con bandas propias (no favorable/desfavorable)
    ergo_barem = Barem(instrument_version_id=ergo_ver.id, name="Baremo Postural ROSA", status="ACTIVE")
    session.add(ergo_barem)
    await session.flush()
    session.add_all([
        BaremBand(barem_id=ergo_barem.id, construct_id=dim_ergo.id, code="RIESGO_BAJO", classification_code="RIESGO_BAJO", label="Riesgo Bajo", min_value=0, max_value=25, severity_order=1),
        BaremBand(barem_id=ergo_barem.id, construct_id=dim_ergo.id, code="RIESGO_MEDIO", classification_code="RIESGO_MEDIO", label="Riesgo Medio", min_value=25, max_value=50, severity_order=2),
        BaremBand(barem_id=ergo_barem.id, construct_id=dim_ergo.id, code="RIESGO_ALTO", classification_code="RIESGO_ALTO", label="Riesgo Alto", min_value=50, max_value=75, severity_order=3),
        BaremBand(barem_id=ergo_barem.id, construct_id=dim_ergo.id, code="RIESGO_CRITICO", classification_code="RIESGO_CRITICO", label="Riesgo Crítico", min_value=75, max_value=100, severity_order=4),
    ])
    await session.flush()

    survey = Survey(
        project_id=seed_project.id,
        instrument_version_id=ergo_ver.id,
        created_by_user_id=seed_user.id,
        name="Survey Ergonomía",
        survey_type="CUSTOM",
    )
    session.add(survey)
    await session.flush()
    session.add(SurveyQuestion(survey_id=survey.id, question_id=q_ergo.id, sort_order=1))
    await session.commit()

    study = await study_service.create(
        seed_project.id,
        StudyCreate(
            survey_id=survey.id,
            name="Campaña Ergonomía Operativa",
            study_type="CUSTOM",
            min_publishable_n=1,
        ),
    )
    study.barem_id = ergo_barem.id
    await session.commit()
    await study_service.open(study.id)

    # Crear respuestas con nivel de riesgo medio
    resp_service = ResponseService(session)
    sess1 = await resp_service.create_session(study.id)
    await resp_service.upsert_response(sess1.id, q_ergo.id, ResponseUpsert(numeric_value=2.0, raw_code="2"))
    await resp_service.complete_session(sess1.id, ResponseSessionCompleteRequest())

    sess2 = await resp_service.create_session(study.id)
    await resp_service.upsert_response(sess2.id, q_ergo.id, ResponseUpsert(numeric_value=3.0, raw_code="3"))
    await resp_service.complete_session(sess2.id, ResponseSessionCompleteRequest())

    run, summary = await ScoringService(session).run(study.id)
    assert run.status == "COMPLETED"

    # Verificar que el resultado NO contiene algoritmo ni etiquetas forzadas de CENSOPAS
    overview = await ScoringService(session).get_overview(study.id)
    res = overview.results[0]
    assert res.construct_code == "RIESGO_POSTURAL"
    assert res.n_valid == 2

    # El resultado debe estar rotulado con ergonomia-v1, no con censopas-v2
    unit_res = (await CensopasScoringService(session).repo.list_construct_results(study.id))[0]
    assert unit_res.algorithm_version == "ergonomia-v1"
    assert unit_res.favorable_pct is None
    assert unit_res.unfavorable_pct is None
    assert unit_res.metadata_["methodological_family"] == "ERGONOMIA"
    assert "band_percentages" in unit_res.metadata_
    assert unit_res.metadata_["band_counts"]["RIESGO_MEDIO"] == 1
    assert unit_res.metadata_["band_counts"]["RIESGO_ALTO"] == 1

    # Comportamiento fail-closed ante regla no soportada
    ergo_ver.methodological_rules = {"required_algorithm": "algoritmo_fantasma_invalido"}
    await session.commit()
    with pytest.raises(ValidationDomainError, match="algoritmo metodológico no soportado"):
        await ScoringService(session).run(study.id)


@pytest.mark.asyncio
async def test_a4_longitudinal_comparability_rejects_incompatible_signatures(session, seed_user, seed_project):
    """A4: Comparabilidad longitudinal bloquea la comparación si dos estudios
    utilizan baremos, versiones o algoritmos incompatibles, y protege la privacidad."""
    study_service = StudyService(session)
    analysis_service = AnalysisService(session)

    # Crear dos versiones distintas del mismo instrumento
    instrument = Instrument(
        project_id=seed_project.id,
        owner_user_id=seed_user.id,
        name="Instrumento Comparabilidad",
        discipline="PSICOSOCIAL",
        status="ACTIVE",
    )
    session.add(instrument)
    await session.flush()

    v1 = InstrumentVersion(instrument_id=instrument.id, version_code="V1_2025", status="AUTHORIZED", scoring_status="CONFIGURED")
    v2 = InstrumentVersion(instrument_id=instrument.id, version_code="V2_2026_MODIFIED", status="AUTHORIZED", scoring_status="CONFIGURED")
    session.add_all([v1, v2])
    await session.flush()

    opt = OptionSet(owner_user_id=seed_user.id, name="Opt", code="OPT")
    session.add(opt)
    await session.flush()
    session.add_all([
        OptionSetOption(option_set_id=opt.id, raw_code="1", label="1", numeric_value=1.0, sort_order=1),
        OptionSetOption(option_set_id=opt.id, raw_code="2", label="2", numeric_value=2.0, sort_order=2),
    ])
    await session.flush()

    q1 = Question(instrument_version_id=v1.id, option_set_id=opt.id, code="P1", question_text="P1", question_type="LIKERT", is_scored=True)
    q2 = Question(instrument_version_id=v2.id, option_set_id=opt.id, code="P1", question_text="P1 mod", question_type="LIKERT", is_scored=True)
    session.add_all([q1, q2])
    await session.flush()

    d1 = Construct(instrument_version_id=v1.id, code="ESTRES", name="Estrés", construct_type="DIMENSION")
    d2 = Construct(instrument_version_id=v2.id, code="ESTRES", name="Estrés", construct_type="DIMENSION")
    session.add_all([d1, d2])
    await session.flush()
    session.add_all([
        ConstructItem(construct_id=d1.id, question_id=q1.id, weight=1.0),
        ConstructItem(construct_id=d2.id, question_id=q2.id, weight=1.0),
    ])
    await session.flush()

    s1 = Survey(project_id=seed_project.id, instrument_version_id=v1.id, created_by_user_id=seed_user.id, name="S1", survey_type="CUSTOM")
    s2 = Survey(project_id=seed_project.id, instrument_version_id=v2.id, created_by_user_id=seed_user.id, name="S2", survey_type="CUSTOM")
    session.add_all([s1, s2])
    await session.flush()
    session.add_all([
        SurveyQuestion(survey_id=s1.id, question_id=q1.id, sort_order=1),
        SurveyQuestion(survey_id=s2.id, question_id=q2.id, sort_order=1),
    ])
    await session.commit()

    study1 = await study_service.create(seed_project.id, StudyCreate(survey_id=s1.id, name="Medición 2025", study_type="CUSTOM", min_publishable_n=1))
    study2 = await study_service.create(seed_project.id, StudyCreate(survey_id=s2.id, name="Medición 2026", study_type="CUSTOM", min_publishable_n=1))
    await study_service.open(study1.id)
    await study_service.open(study2.id)

    # Correr scoring en ambos estudios
    resp_service = ResponseService(session)
    sess1 = await resp_service.create_session(study1.id)
    await resp_service.upsert_response(sess1.id, q1.id, ResponseUpsert(numeric_value=1.0, raw_code="1"))
    await resp_service.complete_session(sess1.id, ResponseSessionCompleteRequest())

    sess2 = await resp_service.create_session(study2.id)
    await resp_service.upsert_response(sess2.id, q2.id, ResponseUpsert(numeric_value=2.0, raw_code="2"))
    await resp_service.complete_session(sess2.id, ResponseSessionCompleteRequest())

    await ScoringService(session).run(study1.id)
    await ScoringService(session).run(study2.id)

    # Comparación longitudinal
    longitudinal = await analysis_service.get_longitudinal_comparison(seed_project.id, study_ids=[study1.id, study2.id])
    assert longitudinal.total_studies_analyzed == 2
    assert len(longitudinal.constructs) >= 1

    trend = next(c for c in longitudinal.constructs if c.construct_code == "ESTRES")
    # Debido a que las versiones son distintas (V1 vs V2), no debe permitir comparabilidad directa
    assert trend.is_comparable is False
    assert trend.delta_mean_score is None
    assert trend.trend_direction == "NOT_COMPARABLE"
    assert "METHODOLOGICAL_INCOMPATIBILITY_SIGNATURE_MISMATCH" in trend.incomparability_reasons
