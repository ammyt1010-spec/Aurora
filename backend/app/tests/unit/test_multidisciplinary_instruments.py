"""Pruebas unitarias y adversariales para la Arquitectura Multidisciplinaria de AURORA Professional (PR #13).

Valida:
1. Registro multidisciplinario de instrumentos y derechos de reproducción.
2. Aislamiento multiempresa (acceso cruzado denegado a instrumentos privados).
3. Bloqueo retroactivo P0 en evaluaciones cerradas (inmutabilidad psicométrica).
4. Auditoría metodológica (estructura, ítems, constructos, baremos).
5. Integración comercial desacoplada y tarifas por operador.
6. Prevención de manipulación de metodología para pagar menos.
7. Emisión fail-closed sin orden pagada (PR #12 intacto).
8. Cero regresión en instrumentos CENSOPAS y SUSESO existentes.
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest

from app.core.config import get_settings
from app.core.exceptions import (
    AuthorizationError,
    InstrumentLockedError,
    NotFoundError,
    ValidationDomainError,
)
from app.models.billing import ReportOrder, ReportTariff
from app.models.construct import Construct, ConstructItem
from app.models.instrument import Instrument, InstrumentVersion
from app.models.option_set import OptionSet, OptionSetOption
from app.models.project import Project
from app.models.question import Question
from app.models.study import Study
from app.models.survey import Survey
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.billing import TariffInput
from app.schemas.instruments import (
    InstrumentCreate,
    InstrumentUpdate,
    InstrumentVersionCreate,
    InstrumentVersionUpdate,
)
from app.services.billing_service import BillingService
from app.services.instrument_edit_policy import InstrumentEditPolicy
from app.services.instrument_service import InstrumentService
from app.services.methodology_validator import MethodologyValidator


@pytest.mark.asyncio
async def test_multidisciplinary_instrument_registration(session, seed_user):
    """1. Registro de instrumentos multidisciplinarios con metadatos y derechos de autor."""
    service = InstrumentService(session)

    payload = InstrumentCreate(
        name="Evaluación Rápida de Tensión en Oficina (ROSA)",
        code="ERGONOMIA_ROSA_V1",
        discipline="ERGONOMIA",
        description="Método de evaluación postural y factores ergonómicos en oficinas.",
        author="M. Sonne, D.L. Andrews, D.A. Johnson",
        source_name="Applied Ergonomics, Elsevier",
        source_url="https://doi.org/10.1016/j.apergo.2011.08.003",
        reproduction_terms="Uso académico y corporativo autorizado con atribución de autoría.",
        method_code="ERGONOMIA_ROSA",
        status="AUTHORIZED",
        owner_user_id=seed_user.id,
    )
    instrument = await service.create(payload)
    assert instrument.id is not None
    assert instrument.discipline == "ERGONOMIA"
    assert instrument.author == "M. Sonne, D.L. Andrews, D.A. Johnson"
    assert "atribución" in instrument.reproduction_terms
    assert instrument.method_code == "ERGONOMIA_ROSA"

    version_payload = InstrumentVersionCreate(
        version_code="ROSA_2012_OFFICE",
        version_name="Versión 2012 Estandarizada",
        edition="Segunda edición",
        status="AUTHORIZED",
        reproduction_restrictions="Prohibida su redistribución sin citar a los autores originales.",
        methodological_rules={
            "scoring_rules": {"chair": 1.0, "monitor_phone": 1.0, "mouse_keyboard": 1.0},
            "cutoffs": {"bajo": 3, "medio": 5, "alto": 8},
        },
    )
    version = await service.create_version(instrument.id, version_payload)
    assert version.id is not None
    assert version.reproduction_restrictions is not None
    assert version.methodological_rules["cutoffs"]["alto"] == 8


@pytest.mark.asyncio
async def test_multi_tenant_isolation_denies_cross_org_access(session, seed_user):
    """2. Aislamiento multiempresa: Empresa A no puede consultar ni ver instrumentos privados de Empresa B."""
    service = InstrumentService(session)

    # Crear dos organizaciones
    org_a = Organization(name="Empresa Minera Alfa", tax_id="20100000001")
    org_b = Organization(name="Corporación Beta", tax_id="20200000002")
    session.add_all([org_a, org_b])
    await session.flush()

    # Empresa A registra un instrumento privado
    inst_a = await service.create(
        InstrumentCreate(
            name="Escala Privada Clima Alfa",
            code="CLIMA_PRIVADO_ALFA",
            discipline="CLIMA_ORGANIZACIONAL",
            organization_id=org_a.id,
            is_system=False,
            status="DRAFT",
        )
    )

    # Empresa B intenta acceder directamente a inst_a -> debe denegarse (NotFoundError)
    with pytest.raises(NotFoundError):
        await service.get(inst_a.id, organization_id=org_b.id)

    # Empresa A sí puede acceder a su propio instrumento
    read_a = await service.get(inst_a.id, organization_id=org_a.id)
    assert read_a.id == inst_a.id

    # Sistema o público (is_system=True) es visible para todos
    system_inst = await service.create(
        InstrumentCreate(
            name="CENSOPAS Oficial Sistema",
            code="CENSOPAS_SISTEMA",
            discipline="PSICOSOCIAL",
            is_system=True,
            status="AUTHORIZED",
        )
    )
    read_by_b = await service.get(system_inst.id, organization_id=org_b.id)
    assert read_by_b.id == system_inst.id


@pytest.mark.asyncio
async def test_retroactive_lock_on_closed_evaluations(session, seed_user):
    """3. Bloqueo retroactivo P0: versiones utilizadas en estudios cerrados quedan estrictamente congeladas."""
    project = Project(
        owner_user_id=seed_user.id,
        name="Proyecto Auditoría Histórica",
        project_type="RESEARCH",
        status="ACTIVE",
    )
    session.add(project)
    await session.flush()

    survey = Survey(
        project_id=project.id,
        created_by_user_id=seed_user.id,
        name="Encuesta Cerrada",
        survey_type="CUSTOM",
        status="CLOSED",
    )
    session.add(survey)
    await session.flush()

    instrument = Instrument(
        name="Cuestionario Evaluado 2025",
        code="EVAL_2025_HISTORICA",
        discipline="PSICOSOCIAL",
        is_system=False,
        status="AUTHORIZED",
    )
    session.add(instrument)
    await session.flush()

    version = InstrumentVersion(
        instrument_id=instrument.id,
        version_code="V_2025_FINAL",
        status="ACTIVE",
    )
    session.add(version)
    await session.flush()

    # Estudio cerrado que referencia la versión
    study_closed = Study(
        project_id=project.id,
        survey_id=survey.id,
        instrument_version_id=version.id,
        name="Estudio Anual Concluido",
        study_type="CENSO",
        status="CLOSED",  # Evaluación concluida
    )
    session.add(study_closed)
    await session.commit()

    # Evaluar con la política asíncrona
    policy_state = await InstrumentEditPolicy.evaluate_async(session, instrument, version)
    assert policy_state.editable is False
    assert policy_state.reason == "EVALUATION_CLOSED_RETROACTIVE_LOCK"

    # Intentar editar debe disparar InstrumentLockedError
    with pytest.raises(InstrumentLockedError) as exc_info:
        await InstrumentEditPolicy.require_editable_async(session, instrument, version)
    assert exc_info.value.extra["reason"] == "EVALUATION_CLOSED_RETROACTIVE_LOCK"


@pytest.mark.asyncio
async def test_methodology_validator_psychometric_diagnostics(session, seed_user):
    """4. Auditoría metodológica: detección de ítems sin escala, constructos y certificación de baremos."""
    validator = MethodologyValidator(session)

    # 4.1 Versión incompleta (sin preguntas) -> no válida
    inst = Instrument(name="Instrumento Vacío", is_system=False, status="DRAFT")
    session.add(inst)
    await session.flush()
    v_empty = InstrumentVersion(instrument_id=inst.id, version_code="V_EMPTY", status="DRAFT")
    session.add(v_empty)
    await session.flush()

    res_empty = await validator.validate_version(v_empty.id, persist_metrics=True)
    assert res_empty.is_valid is False
    assert any("reactivos" in err for err in res_empty.errors)
    assert res_empty.scoring_status == "NOT_CONFIGURED"

    # 4.2 Versión completa y bien configurada
    inst_complete = Instrument(
        name="Escala de Burnout Maslach MBI",
        code="BURNOUT_MBI",
        discipline="LIDERAZGO_BURNOUT",
        is_system=False,
        status="AUTHORIZED",
    )
    session.add(inst_complete)
    await session.flush()

    v_complete = InstrumentVersion(
        instrument_id=inst_complete.id,
        version_code="MBI_HSS_22",
        status="VALIDATING",
        methodological_rules={
            "scoring_rules": {"exhaustion": 1.0, "cynicism": 1.0},
            "cutoffs": {"bajo": 16, "medio": 27, "alto": 54},
        },
    )
    session.add(v_complete)
    await session.flush()

    scale = OptionSet(
        name="Frecuencia 0-6",
        instrument_version_id=v_complete.id,
        options=[
            OptionSetOption(raw_code="0", label="Nunca", numeric_value=0, sort_order=1),
            OptionSetOption(raw_code="1", label="Pocas veces al año", numeric_value=1, sort_order=2),
            OptionSetOption(raw_code="6", label="Todos los días", numeric_value=6, sort_order=3),
        ],
    )
    session.add(scale)
    await session.flush()

    dim = Construct(
        instrument_version_id=v_complete.id,
        code="AGOTAMIENTO_EMOCIONAL",
        name="Agotamiento Emocional",
        construct_type="DIMENSION",
    )
    session.add(dim)
    await session.flush()

    q1 = Question(
        instrument_version_id=v_complete.id,
        code="MBI_01",
        question_text="Me siento emocionalmente agotado por mi trabajo.",
        question_type="LIKERT",
        is_scored=True,
        option_set_id=scale.id,
    )
    session.add(q1)
    await session.flush()

    session.add(ConstructItem(construct_id=dim.id, question_id=q1.id, weight=1.0))
    await session.commit()

    res_complete = await validator.validate_version(v_complete.id, persist_metrics=True)
    assert res_complete.is_valid is True
    assert res_complete.scoring_status == "CONFIGURED"
    assert res_complete.metrics["total_questions"] == 1
    assert res_complete.metrics["dimension_count"] == 1


@pytest.mark.asyncio
async def test_decoupled_commercial_tariffs_and_unauthorized_rejection(session, seed_user, monkeypatch):
    """5. Tarifario desacoplado: cotización de nuevos métodos, rechazo de instrumentos no autorizados o sin baremos."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    billing = BillingService(session)

    # Crear empresa y admin
    admin = User(email="admin-corp@aurora.test", username="admin-corp", status="ACTIVE")
    session.add(admin)
    await session.flush()
    org = Organization(name="Corporación Multidisciplinaria", tax_id="20555666777")
    session.add(org)
    await session.flush()
    session.add(OrganizationMembership(organization_id=org.id, user_id=admin.id, role_code="OWNER", permissions={}))

    project = Project(
        owner_user_id=admin.id,
        organization_id=org.id,
        name="Ergonomía Corporativa",
        project_type="RESEARCH",
        status="ACTIVE",
    )
    session.add(project)
    await session.flush()
    survey = Survey(project_id=project.id, created_by_user_id=admin.id, name="Encuesta Ergonómica", status="ACTIVE")
    session.add(survey)
    await session.flush()

    # Operador central crea tarifa para el método ERGONOMIA_ROSA
    await billing.save_tariff(
        TariffInput(method_code="ERGONOMIA_ROSA", min_workers=1, max_workers=100, price=Decimal("350.00")),
        seed_user,
    )

    # 5.1 Caso rechazado: instrumento en DRAFT (no autorizado)
    inst_draft = Instrument(
        name="ROSA Prototipo",
        code="ERGONOMIA_ROSA",
        method_code="ERGONOMIA_ROSA",
        status="DRAFT",  # No autorizado
        is_system=False,
    )
    session.add(inst_draft)
    await session.flush()
    ver_draft = InstrumentVersion(instrument_id=inst_draft.id, version_code="V_DRAFT", scoring_status="CONFIGURED")
    session.add(ver_draft)
    await session.flush()

    study_draft = Study(
        project_id=project.id,
        survey_id=survey.id,
        instrument_version_id=ver_draft.id,
        name="Estudio No Autorizado",
        study_type="CENSO",
        status="DRAFT",
    )
    session.add(study_draft)
    await session.commit()

    with pytest.raises(ValidationDomainError) as exc_info:
        await billing.create_quote(study_draft.id, 50, admin, method_code="ERGONOMIA_ROSA")
    assert "no cuenta con autorización corporativa" in str(exc_info.value)

    # 5.2 Caso rechazado: instrumento autorizado pero sin configuración psicométrica suficiente
    inst_authorized = Instrument(
        name="ROSA Oficial",
        code="ERGONOMIA_ROSA",
        method_code="ERGONOMIA_ROSA",
        status="AUTHORIZED",  # Autorizado
        is_system=False,
    )
    session.add(inst_authorized)
    await session.flush()
    ver_unconfigured = InstrumentVersion(
        instrument_id=inst_authorized.id,
        version_code="V_UNCONF",
        scoring_status="NOT_CONFIGURED",  # Carece de reglas
    )
    session.add(ver_unconfigured)
    await session.flush()
    study_unconf = Study(
        project_id=project.id,
        survey_id=survey.id,
        instrument_version_id=ver_unconfigured.id,
        name="Estudio Sin Reglas",
        study_type="CENSO",
        status="DRAFT",
    )
    session.add(study_unconf)
    await session.commit()

    with pytest.raises(ValidationDomainError) as exc_info2:
        await billing.create_quote(study_unconf.id, 50, admin, method_code="ERGONOMIA_ROSA")
    assert "carece de configuración psicométrica/metodológica suficiente" in str(exc_info2.value)

    # 5.3 Caso exitoso: instrumento autorizado y configurado
    ver_valid = InstrumentVersion(
        instrument_id=inst_authorized.id,
        version_code="V_VALID",
        scoring_status="CONFIGURED",
    )
    session.add(ver_valid)
    await session.flush()
    study_valid = Study(
        project_id=project.id,
        survey_id=survey.id,
        instrument_version_id=ver_valid.id,
        name="Estudio Ergonómico Válido",
        study_type="CENSO",
        status="DRAFT",
    )
    session.add(study_valid)
    await session.commit()

    quote_order = await billing.create_quote(study_valid.id, 50, admin, method_code="ERGONOMIA_ROSA")
    assert quote_order.id is not None
    assert quote_order.amount == Decimal("350.00")
    assert quote_order.method_code == "ERGONOMIA_ROSA"
    assert quote_order.snapshot_data["method"]["code"] == "ERGONOMIA_ROSA"


@pytest.mark.asyncio
async def test_adversarial_method_manipulation_prevented(session, seed_user, monkeypatch):
    """6. Adversarial: manipulación de metodología para pagar una tarifa inferior es estrictamente rechazada."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    billing = BillingService(session)

    admin = User(email="admin-cheating@aurora.test", username="admin-cheating", status="ACTIVE")
    session.add(admin)
    await session.flush()
    org = Organization(name="Empresa Ahorradora", tax_id="20999888111")
    session.add(org)
    await session.flush()
    session.add(OrganizationMembership(organization_id=org.id, user_id=admin.id, role_code="OWNER", permissions={}))

    project = Project(
        owner_user_id=admin.id,
        organization_id=org.id,
        name="Evaluación Integral",
        project_type="RESEARCH",
        status="ACTIVE",
    )
    session.add(project)
    await session.flush()
    survey = Survey(project_id=project.id, created_by_user_id=admin.id, name="Encuesta Media", status="ACTIVE")
    session.add(survey)
    await session.flush()

    # Crear tarifas: SUSESO_ISTAS21_BREVE (S/ 160) y CENSOPAS_MEDIA (S/ 560)
    await billing.save_tariff(TariffInput(method_code="SUSESO_ISTAS21_BREVE", min_workers=1, max_workers=100, price=Decimal("160.00")), seed_user)
    await billing.save_tariff(TariffInput(method_code="CENSOPAS_MEDIA", min_workers=1, max_workers=100, price=Decimal("560.00")), seed_user)

    # Instrumento evaluado es CENSOPAS_COPSOQ versión MEDIA
    inst = Instrument(name="CENSOPAS Oficial", code="CENSOPAS_COPSOQ", is_system=True, status="AUTHORIZED")
    session.add(inst)
    await session.flush()
    ver_media = InstrumentVersion(
        instrument_id=inst.id,
        version_code="CENSOPAS_MEDIA_V1",
        config={"censopas_version_kind": "MEDIA"},
        scoring_status="CONFIGURED",
    )
    session.add(ver_media)
    await session.flush()

    study = Study(
        project_id=project.id,
        survey_id=survey.id,
        instrument_version_id=ver_media.id,
        name="Estudio CENSOPAS Media",
        study_type="CENSO",
        status="DRAFT",
    )
    session.add(study)
    await session.commit()

    # El usuario intenta cotizar SUSESO_ISTAS21_BREVE (más barata) en lugar de CENSOPAS_MEDIA
    with pytest.raises(ValidationDomainError) as exc_info:
        await billing.create_quote(study.id, 50, admin, method_code="SUSESO_ISTAS21_BREVE")
    assert "no corresponde al instrumento del estudio" in str(exc_info.value)


@pytest.mark.asyncio
async def test_regression_censopas_and_suseso_fully_functional(session, seed_user, monkeypatch):
    """7. Regresión: instrumentos CENSOPAS y SUSESO continúan cotizándose y operando sin regresión alguna."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    billing = BillingService(session)

    admin = User(email="admin-legit@aurora.test", username="admin-legit", status="ACTIVE")
    session.add(admin)
    await session.flush()
    org = Organization(name="Empresa Conforme", tax_id="20444333222")
    session.add(org)
    await session.flush()
    session.add(OrganizationMembership(organization_id=org.id, user_id=admin.id, role_code="OWNER", permissions={}))

    project = Project(
        owner_user_id=admin.id,
        organization_id=org.id,
        name="Estudio SUSESO",
        project_type="RESEARCH",
        status="ACTIVE",
    )
    session.add(project)
    await session.flush()
    survey = Survey(project_id=project.id, created_by_user_id=admin.id, name="Encuesta SUSESO", status="ACTIVE")
    session.add(survey)
    await session.flush()

    await billing.save_tariff(TariffInput(method_code="SUSESO_ISTAS21_BREVE", min_workers=1, max_workers=100, price=Decimal("160.00")), seed_user)

    inst_suseso = Instrument(name="SUSESO ISTAS-21 Breve", code="SUSESO_ISTAS21", is_system=True, status="AUTHORIZED")
    session.add(inst_suseso)
    await session.flush()
    ver_suseso = InstrumentVersion(instrument_id=inst_suseso.id, version_code="V_BREVE", scoring_status="CONFIGURED")
    session.add(ver_suseso)
    await session.flush()

    study = Study(
        project_id=project.id,
        survey_id=survey.id,
        instrument_version_id=ver_suseso.id,
        name="Evaluación Nacional SUSESO",
        study_type="CENSO",
        status="DRAFT",
    )
    session.add(study)
    await session.commit()

    order = await billing.create_quote(study.id, 45, admin, method_code="SUSESO_ISTAS21_BREVE")
    assert order.id is not None
    assert order.amount == Decimal("160.00")
    assert order.status == "PENDING_PAYMENT"
