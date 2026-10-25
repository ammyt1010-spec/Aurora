"""PR #14 CODEX Corrective Audit: Adversarial Integration Test Suite.

Covers the 8 mandatory security, methodological, multi-tenant and commercial integrity vectors:
1. Suplantación de organización (Org Impersonation / IDOR).
2. Vinculación de instrumentos entre empresas (Cross-Company Linking).
3. Autorización arbitraria de instrumentos (Arbitrary Authorization).
4. Falsificación de estado de puntuación (Scoring Status Falsification).
5. Alteración retroactiva de versiones en estudios concluidos (EVALUATION_CLOSED_RETROACTIVE_LOCK).
6. Manipulación de tarifas por instrumento (Tariff Manipulation).
7. Acceso a información privada de otra empresa (Multi-Tenant Private Access).
8. Regresión de CENSOPAS y SUSESO (Zero Regression).
"""

from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    InstrumentLockedError,
    ValidationDomainError,
)
from app.core.security import create_access_token
from app.main import app
from app.models.billing import ReportTariff, ReportOrder
from app.models.construct import Construct, ConstructItem
from app.models.instrument import Instrument, InstrumentVersion
from app.models.project import Project
from app.models.question import Question
from app.models.scoring import ScoringRule
from app.models.study import Study
from app.models.survey import Survey
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.billing import TariffInput
from app.services.billing_service import BillingService


@pytest.fixture(autouse=True)
def _isolate_operator_user(monkeypatch):
    """Ensure newly created tenant user IDs (1, 2, ...) are not treated as central operator."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", 999999)


async def _create_test_user(session, email: str, username: str) -> User:
    user = User(email=email, username=username, status="ACTIVE", session_version=1)
    session.add(user)
    await session.flush()
    return user


async def _setup_company(session, prefix: str, owner_email: str):
    user = await _create_test_user(session, owner_email, prefix.lower())
    org = Organization(name=f"Empresa {prefix}", tax_id=f"20{abs(hash(prefix)) % 100000000:08d}")
    session.add(org)
    await session.flush()
    session.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role_code="OWNER"))
    proj = Project(owner_user_id=user.id, organization_id=org.id, name=f"Proj {prefix}", project_type="RESEARCH")
    session.add(proj)
    await session.flush()
    surv = Survey(project_id=proj.id, created_by_user_id=user.id, name=f"Surv {prefix}", survey_type="CUSTOM")
    session.add(surv)
    await session.flush()
    study = Study(project_id=proj.id, survey_id=surv.id, name=f"Study {prefix}", study_type="RESEARCH", status="OPEN")
    session.add(study)
    await session.commit()
    return user, org, proj, study


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, session_version=user.session_version)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_01_suplantacion_de_organizacion_idor(session, monkeypatch):
    """1. Suplantación de organización: tenant A no puede crear instrumentos ni asignar IDs de organización B."""
    user_a, org_a, proj_a, _ = await _setup_company(session, "Alfa", "owner-alfa-01@aurora.pe")
    user_b, org_b, proj_b, _ = await _setup_company(session, "Beta", "owner-beta-01@aurora.pe")

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Intento 1: User A intenta crear instrumento especificando organization_id de Org B
            payload_spoof = {
                "name": "Instrumento Malicioso",
                "organization_id": org_b.id,
                "discipline": "ERGONOMIA",
            }
            res1 = await client.post("/api/v1/instruments", json=payload_spoof, headers=_auth_headers(user_a))
            assert res1.status_code == 403, f"Esperado 403, obtenido {res1.status_code}: {res1.text}"
            assert "organizaci" in res1.text and ("permisos" in res1.text or "acceso" in res1.text)

            # Intento 2: User A intenta crear instrumento dentro del proyecto de Org B
            payload_proj_spoof = {
                "name": "Instrumento Invasor",
                "discipline": "PSICOSOCIAL",
            }
            res2 = await client.post(
                f"/api/v1/projects/{proj_b.id}/instruments",
                json=payload_proj_spoof,
                headers=_auth_headers(user_a),
            )
            assert res2.status_code == 403, f"Esperado 403, obtenido {res2.status_code}: {res2.text}"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_02_vinculacion_instrumentos_entre_empresas_rechazada(session):
    """2. Vinculación de instrumentos entre empresas: estudio de empresa A no puede vincular instrumento privado de B."""
    user_a, org_a, proj_a, study_a = await _setup_company(session, "AlfaVinc", "owner-alfa-02@aurora.pe")
    user_b, org_b, proj_b, study_b = await _setup_company(session, "BetaVinc", "owner-beta-02@aurora.pe")

    # Crear instrumento privado para Empresa B
    inst_b = Instrument(
        project_id=proj_b.id,
        owner_user_id=user_b.id,
        organization_id=org_b.id,
        name="Instrumento Privado Beta",
        discipline="ERGONOMIA",
        status="ACTIVE",
        is_system=False,
    )
    session.add(inst_b)
    await session.flush()
    ver_b = InstrumentVersion(
        instrument_id=inst_b.id,
        version_code="v1.0",
        version_name="Beta Ergonomia v1",
        status="ACTIVE",
        scoring_status="CONFIGURED",
    )
    session.add(ver_b)
    await session.commit()

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # User A intenta vincular la versión privada de Beta a su propio estudio en Alfa
            res = await client.post(
                f"/api/v1/studies/{study_a.id}/instruments/{ver_b.id}",
                headers=_auth_headers(user_a),
            )
            assert res.status_code == 403, f"Esperado 403, obtenido {res.status_code}: {res.text}"
            assert "FORBIDDEN" in res.text or "pertenece" in res.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_03_autorizacion_arbitraria_de_instrumentos_bloqueada(session, monkeypatch):
    """3. Autorización arbitraria: ningún tenant puede pasar a AUTHORIZED ni el operador sin scoring configurado."""
    user_a, org_a, proj_a, _ = await _setup_company(session, "AlfaAuth", "owner-alfa-03@aurora.pe")
    operator = await _create_test_user(session, "central-operator@aurora.pe", "central_op")
    await session.commit()

    monkeypatch.setattr(get_settings(), "billing_operator_user_id", operator.id)

    # Crear instrumento borrador de tenant A
    inst_a = Instrument(
        project_id=proj_a.id,
        owner_user_id=user_a.id,
        organization_id=org_a.id,
        name="Clima Laboral Alfa",
        discipline="CLIMA_ORGANIZACIONAL",
        status="DRAFT",
        is_system=False,
    )
    session.add(inst_a)
    await session.flush()
    ver_a = InstrumentVersion(
        instrument_id=inst_a.id,
        version_code="v1",
        version_name="Clima v1",
        status="DRAFT",
        scoring_status="NOT_CONFIGURED",
    )
    session.add(ver_a)
    await session.commit()

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Tenant intenta auto-autorizar su instrumento
            res_tenant = await client.post(
                f"/api/v1/instruments/{inst_a.id}/status",
                json={"status": "AUTHORIZED", "notes": "Auto-aprobado por tenant"},
                headers=_auth_headers(user_a),
            )
            assert res_tenant.status_code == 403, f"Esperado 403, obtenido {res_tenant.status_code}: {res_tenant.text}"
            assert "Solo el operador central o comité metodológico" in res_tenant.text

            # 2. Operador intenta autorizar, pero la versión carece de scoring_status="CONFIGURED"
            res_op = await client.post(
                f"/api/v1/instruments/{inst_a.id}/status",
                json={"status": "AUTHORIZED", "notes": "Aprobación prematura"},
                headers=_auth_headers(operator),
            )
            assert res_op.status_code == 422, f"Esperado 422, obtenido {res_op.status_code}: {res_op.text}"
            assert "carezcan de configuración psicométrica completa" in res_op.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_04_falsificacion_estado_puntuacion_bloqueada(session):
    """4. Falsificación de estado de puntuación: tenant no puede asignar manualmente scoring_status=CONFIGURED."""
    user_a, org_a, proj_a, _ = await _setup_company(session, "AlfaScore", "owner-alfa-04@aurora.pe")

    inst_a = Instrument(
        project_id=proj_a.id,
        owner_user_id=user_a.id,
        organization_id=org_a.id,
        name="Seguridad Alfa",
        discipline="SEGURIDAD_SALUD",
        status="DRAFT",
    )
    session.add(inst_a)
    await session.flush()
    ver_a = InstrumentVersion(
        instrument_id=inst_a.id,
        version_code="v1",
        version_name="Seguridad v1",
        status="DRAFT",
        scoring_status="NOT_CONFIGURED",
    )
    session.add(ver_a)
    await session.commit()

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.patch(
                f"/api/v1/instrument-versions/{ver_a.id}",
                json={"scoring_status": "CONFIGURED"},
                headers=_auth_headers(user_a),
            )
            assert res.status_code == 403, f"Esperado 403, obtenido {res.status_code}: {res.text}"
            assert "no puede asignarse manualmente" in res.text

            # Verificar en base de datos que no cambió
            await session.refresh(ver_a)
            assert ver_a.scoring_status == "NOT_CONFIGURED"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_05_alteracion_retroactiva_estudios_concluidos(session):
    """5. Alteración retroactiva: versiones con evaluaciones cerradas quedan bloqueadas (EVALUATION_CLOSED_RETROACTIVE_LOCK)."""
    user_a, org_a, proj_a, study_a = await _setup_company(session, "AlfaClosed", "owner-alfa-05@aurora.pe")

    inst_a = Instrument(
        project_id=proj_a.id,
        owner_user_id=user_a.id,
        organization_id=org_a.id,
        name="Liderazgo Alfa",
        discipline="LIDERAZGO_BURNOUT",
        method_code="BURNOUT_MBI",
        status="ACTIVE",
    )
    session.add(inst_a)
    await session.flush()
    ver_a = InstrumentVersion(
        instrument_id=inst_a.id,
        version_code="v1.0",
        version_name="MBI v1",
        status="ACTIVE",
        scoring_status="CONFIGURED",
    )
    session.add(ver_a)
    await session.flush()

    # Vincular al estudio y cerrar el estudio
    study_a.instrument_version_id = ver_a.id
    study_a.status = "CLOSED"
    await session.commit()

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Intento de modificar versión histórica
            res_ver = await client.patch(
                f"/api/v1/instrument-versions/{ver_a.id}",
                json={"version_name": "Nombre Alterado Post-Cierre"},
                headers=_auth_headers(user_a),
            )
            assert res_ver.status_code == 409, f"Esperado 409, obtenido {res_ver.status_code}: {res_ver.text}"
            assert res_ver.json().get("reason") == "EVALUATION_CLOSED_RETROACTIVE_LOCK"

            # 2. Intento de modificar campos estructurales del instrumento (method_code)
            res_inst = await client.patch(
                f"/api/v1/instruments/{inst_a.id}",
                json={"method_code": "OTRO_METODO_ALTERADO"},
                headers=_auth_headers(user_a),
            )
            assert res_inst.status_code == 409, f"Esperado 409, obtenido {res_inst.status_code}: {res_inst.text}"
            assert res_inst.json().get("reason") == "EVALUATION_CLOSED_RETROACTIVE_LOCK"

            # 3. Intento de alterar estado del instrumento
            res_stat = await client.post(
                f"/api/v1/instruments/{inst_a.id}/status",
                json={"status": "DRAFT"},
                headers=_auth_headers(user_a),
            )
            assert res_stat.status_code == 409, f"Esperado 409, obtenido {res_stat.status_code}: {res_stat.text}"
            assert res_stat.json().get("reason") == "EVALUATION_CLOSED_RETROACTIVE_LOCK"

            # 4. Re-validación para fines de auditoría genera dictamen sin mutar metadatos históricos
            res_val = await client.post(
                f"/api/v1/instrument-versions/{ver_a.id}/validate",
                headers=_auth_headers(user_a),
            )
            assert res_val.status_code == 200, f"Esperado 200, obtenido {res_val.status_code}: {res_val.text}"
            val_data = res_val.json()
            assert any("EVALUATION_CLOSED_RETROACTIVE_LOCK" in w for w in val_data.get("warnings", []))
            assert val_data.get("metrics", {}).get("historical_version_locked") is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_06_manipulacion_de_tarifas_por_instrumento_rechazada(session, monkeypatch):
    """6. Manipulación de tarifas: las tarifas vinculadas a instrumentos específicos están aisladas y no pueden secuestrarse."""
    user_a, org_a, proj_a, study_a = await _setup_company(session, "AlfaTariff", "owner-alfa-06@aurora.pe")
    user_b, org_b, proj_b, study_b = await _setup_company(session, "BetaTariff", "owner-beta-06@aurora.pe")
    operator = await _create_test_user(session, "operator-tariff@aurora.pe", "op_tariff")
    await session.commit()

    monkeypatch.setattr(get_settings(), "billing_operator_user_id", operator.id)

    # Instrumento A (Alfa)
    inst_a = Instrument(
        project_id=proj_a.id,
        owner_user_id=user_a.id,
        organization_id=org_a.id,
        name="Instrumento A",
        method_code="METODO_ESPECIAL_A",
        status="AUTHORIZED",
        is_system=False,
    )
    session.add(inst_a)
    await session.flush()
    ver_a = InstrumentVersion(
        instrument_id=inst_a.id,
        version_code="v1",
        version_name="v1",
        status="ACTIVE",
        scoring_status="CONFIGURED",
    )
    session.add(ver_a)

    # Instrumento B (Beta)
    inst_b = Instrument(
        project_id=proj_b.id,
        owner_user_id=user_b.id,
        organization_id=org_b.id,
        name="Instrumento B",
        method_code="METODO_ESPECIAL_B",
        status="AUTHORIZED",
        is_system=False,
    )
    session.add(inst_b)
    await session.flush()
    ver_b = InstrumentVersion(
        instrument_id=inst_b.id,
        version_code="v1",
        version_name="v1",
        status="ACTIVE",
        scoring_status="CONFIGURED",
    )
    session.add(ver_b)

    study_a.instrument_version_id = ver_a.id
    study_b.instrument_version_id = ver_b.id
    await session.commit()

    billing = BillingService(session)

    # Creamos una tarifa específica EXCLUSIVAMENTE para Instrumento B
    tariff_b = await billing.save_tariff(
        TariffInput(
            method_code="METODO_ESPECIAL_B",
            instrument_id=inst_b.id,
            min_workers=1,
            max_workers=100,
            price=Decimal("250.00"),
        ),
        operator,
    )

    # Intento 1: Empresa A intenta cotizar con su estudio (Instrumento A) usando el método de B
    with pytest.raises(ValidationDomainError) as exc_info:
        await billing.create_quote(study_a.id, 50, user_a, method_code="METODO_ESPECIAL_A")
    assert (
        "Metodología de informe desconocida" in str(exc_info.value)
        or "No existe una tarifa autorizada" in str(exc_info.value)
    )

    # Intento 2: Instrumento A cambia scoring_status a NOT_CONFIGURED -> se rechaza cotización
    ver_a.scoring_status = "NOT_CONFIGURED"
    await session.commit()

    tariff_a = await billing.save_tariff(
        TariffInput(
            method_code="METODO_ESPECIAL_A",
            instrument_id=inst_a.id,
            min_workers=1,
            max_workers=100,
            price=Decimal("300.00"),
        ),
        operator,
    )

    with pytest.raises(ValidationDomainError) as exc_info:
        await billing.create_quote(study_a.id, 50, user_a, method_code="METODO_ESPECIAL_A")
    assert "scoring_status=CONFIGURED" in str(exc_info.value)

    # Restaurar scoring_status a CONFIGURED -> cotización exitosa con tarifa específica de Instrumento A
    ver_a.scoring_status = "CONFIGURED"
    await session.commit()

    order = await billing.create_quote(study_a.id, 50, user_a, method_code="METODO_ESPECIAL_A")
    assert order.amount == Decimal("300.00")
    assert order.snapshot_data["tariff"]["instrument_id"] == inst_a.id


@pytest.mark.asyncio
async def test_07_acceso_informacion_privada_otra_empresa_bloqueado(session):
    """7. Acceso a información privada: consultar o filtrar instrumentos privados de otra empresa es denegado o aislado."""
    user_a, org_a, proj_a, _ = await _setup_company(session, "AlfaPriv", "owner-alfa-07@aurora.pe")
    user_b, org_b, proj_b, _ = await _setup_company(session, "BetaPriv", "owner-beta-07@aurora.pe")

    # Instrumento privado de Empresa B
    inst_b = Instrument(
        project_id=proj_b.id,
        owner_user_id=user_b.id,
        organization_id=org_b.id,
        name="Instrumento Ultrasecreto Beta",
        discipline="CLIMA_ORGANIZACIONAL",
        status="ACTIVE",
        is_system=False,
    )
    session.add(inst_b)
    await session.commit()

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. User A intenta listar instrumentos especificando organization_id de Beta
            res_list = await client.get(
                f"/api/v1/instruments?organization_id={org_b.id}",
                headers=_auth_headers(user_a),
            )
            assert res_list.status_code == 403, f"Esperado 403, obtenido {res_list.status_code}: {res_list.text}"
            assert "No tienes acceso a la organización solicitada" in res_list.text

            # 2. User A intenta acceder por ID directo al instrumento privado de Beta
            res_get = await client.get(
                f"/api/v1/instruments/{inst_b.id}",
                headers=_auth_headers(user_a),
            )
            assert res_get.status_code in (403, 404), f"Esperado 403 o 404, obtenido {res_get.status_code}: {res_get.text}"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_08_regresion_censopas_y_suseso_sin_degradacion(session, monkeypatch):
    """8. CENSOPAS y SUSESO: cero regresión en instrumentos del sistema, cotización y protección contra mutaciones arbitrarias."""
    user_a, org_a, proj_a, study_a = await _setup_company(session, "AlfaSys", "owner-alfa-08@aurora.pe")
    operator = await _create_test_user(session, "operator-sys@aurora.pe", "op_sys")
    await session.commit()

    monkeypatch.setattr(get_settings(), "billing_operator_user_id", operator.id)

    # Crear instrumento del sistema CENSOPAS
    inst_censopas = Instrument(
        name="CENSOPAS-COPSOQ Oficial",
        code="CENSOPAS_COPSOQ",
        discipline="PSICOSOCIAL",
        method_code="CENSOPAS_CORTA",
        is_system=True,
        status="AUTHORIZED",
    )
    session.add(inst_censopas)
    await session.flush()
    ver_censopas = InstrumentVersion(
        instrument_id=inst_censopas.id,
        version_code="CORTA",
        version_name="Versión Breve Oficial CENSOPAS",
        status="ACTIVE",
        scoring_status="CONFIGURED",
        config={"censopas_version_kind": "SHORT"},
    )
    session.add(ver_censopas)
    await session.flush()
    # Link only a draft study whose questionnaire represents the selected version.
    study_a.status = "DRAFT"
    survey = await session.get(Survey, study_a.survey_id)
    survey.instrument_version_id = ver_censopas.id
    await session.commit()

    # Guardar tarifa para CENSOPAS_CORTA
    billing = BillingService(session)
    await billing.save_tariff(
        TariffInput(
            method_code="CENSOPAS_CORTA",
            min_workers=1,
            max_workers=100,
            price=Decimal("180.00"),
        ),
        operator,
    )

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Estudio empresarial de Alfa vincula CENSOPAS del sistema exitosamente
            res_link = await client.post(
                f"/api/v1/studies/{study_a.id}/instruments/{ver_censopas.id}",
                headers=_auth_headers(user_a),
            )
            assert res_link.status_code == 200, f"Esperado 200, obtenido {res_link.status_code}: {res_link.text}"
            assert res_link.json()["status"] == "success"

            # 2. Generar cotización oficial para CENSOPAS funciona sin degradación
            quote = await billing.create_quote(study_a.id, 45, user_a, method_code="CENSOPAS_CORTA")
            assert quote.amount == Decimal("180.00")
            assert quote.method_code == "CENSOPAS_CORTA"

            # 3. Intentar mutar el instrumento del sistema por parte del tenant es rechazado
            res_tamper = await client.patch(
                f"/api/v1/instruments/{inst_censopas.id}",
                json={"name": "CENSOPAS Corrompido"},
                headers=_auth_headers(user_a),
            )
            assert res_tamper.status_code in (403, 404, 409)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_09_tarifas_independientes_por_instrumento_mismo_metodo(session, monkeypatch):
    """9. Tarifas por instrumento independientes cuando coincide el código metodológico (Requisito 1)."""
    operator = await _create_test_user(session, "tariff-op-09@aurora.pe", "tariff_op_09")
    await session.commit()
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", operator.id)

    inst_a = Instrument(name="Instrumento Ergo A", discipline="ERGONOMIA", method_code="ROSA", is_system=True, status="AUTHORIZED")
    inst_b = Instrument(name="Instrumento Ergo B", discipline="ERGONOMIA", method_code="ROSA", is_system=True, status="AUTHORIZED")
    session.add_all([inst_a, inst_b])
    await session.commit()
    await session.refresh(inst_a)
    await session.refresh(inst_b)

    billing = BillingService(session)

    # 1. Crear tarifa para Instrumento A (1-50 trabajadores, ROSA)
    tariff_a = await billing.save_tariff(
        TariffInput(
            instrument_id=inst_a.id,
            method_code="ROSA",
            pricing_mode="FIXED",
            min_workers=1,
            max_workers=50,
            price=Decimal("120.00"),
            currency="PEN",
            active=True,
        ),
        operator,
    )
    assert tariff_a.id is not None

    # 2. Crear tarifa independiente para Instrumento B con el mismo method_code y mismo rango de trabajadores (1-50, ROSA)
    # Debe permitirse porque pertenecen a instrumentos distintos
    tariff_b = await billing.save_tariff(
        TariffInput(
            instrument_id=inst_b.id,
            method_code="ROSA",
            pricing_mode="FIXED",
            min_workers=1,
            max_workers=50,
            price=Decimal("150.00"),
            currency="PEN",
            active=True,
        ),
        operator,
    )
    assert tariff_b.id is not None
    assert tariff_b.id != tariff_a.id

    # 3. Intentar crear una tarifa superpuesta para el MISMO instrumento A (25-75, ROSA) -> Debe rechazarse con ConflictError
    with pytest.raises(ConflictError) as exc_info:
        await billing.save_tariff(
            TariffInput(
                instrument_id=inst_a.id,
                method_code="ROSA",
                pricing_mode="FIXED",
                min_workers=25,
                max_workers=75,
                price=Decimal("200.00"),
                currency="PEN",
                active=True,
            ),
            operator,
        )
    assert "superpone" in str(exc_info.value)


@pytest.mark.asyncio
async def test_10_autorizacion_de_versiones_politica_centralizada(session, monkeypatch):
    """10. Política centralizada para autorizar o activar versiones de instrumentos (Requisito 2)."""
    user_a, org_a, proj_a, _ = await _setup_company(session, "AlfaVerAuth", "owner-alfa-10@aurora.pe")
    operator = await _create_test_user(session, "operator-10@aurora.pe", "operator_10")
    await session.commit()
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", operator.id)

    inst = Instrument(
        project_id=proj_a.id,
        owner_user_id=user_a.id,
        organization_id=org_a.id,
        name="Clima Alfa 10",
        discipline="CLIMA_ORGANIZACIONAL",
        status="DRAFT",
    )
    session.add(inst)
    await session.commit()
    await session.refresh(inst)

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Tenant intenta crear una versión directamente en AUTHORIZED -> 422 o 403
            res_create_auth = await client.post(
                f"/api/v1/instruments/{inst.id}/versions",
                json={"version_code": "v_auth", "status": "AUTHORIZED"},
                headers=_auth_headers(user_a),
            )
            assert res_create_auth.status_code in (403, 422)

            # Crear versión legítima en DRAFT
            res_ver = await client.post(
                f"/api/v1/instruments/{inst.id}/versions",
                json={"version_code": "v1.0", "status": "DRAFT"},
                headers=_auth_headers(user_a),
            )
            assert res_ver.status_code == 201
            ver_id = res_ver.json()["id"]

            # 2. Tenant intenta pasar su versión a AUTHORIZED -> 403
            res_patch_tenant = await client.patch(
                f"/api/v1/instrument-versions/{ver_id}",
                json={"status": "AUTHORIZED"},
                headers=_auth_headers(user_a),
            )
            assert res_patch_tenant.status_code == 403

            # 3. Operador intenta autorizar versión sin configuración psicométrica completa -> 422
            res_patch_op_incomplete = await client.patch(
                f"/api/v1/instrument-versions/{ver_id}",
                json={"status": "AUTHORIZED"},
                headers=_auth_headers(operator),
            )
            assert res_patch_op_incomplete.status_code == 422, f"Got {res_patch_op_incomplete.status_code}: {res_patch_op_incomplete.text}"
            assert "scoring_status=CONFIGURED" in res_patch_op_incomplete.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_11_rectificacion_administrativa_auditada_evaluaciones_cerradas(session, monkeypatch):
    """11. Inmutabilidad metodológica y procedimiento auditado de rectificación administrativa (Requisito 3)."""
    user_a, org_a, proj_a, study_a = await _setup_company(session, "AlfaRect", "owner-alfa-11@aurora.pe")
    operator = await _create_test_user(session, "operator-11@aurora.pe", "operator_11")
    await session.commit()
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", operator.id)

    inst_a = Instrument(
        project_id=proj_a.id,
        owner_user_id=user_a.id,
        organization_id=org_a.id,
        name="Instrumento Alfa 11",
        discipline="PSICOSOCIAL",
        method_code="SUSESO_ISTAS21_BREVE",
        author="Autor Original",
        source_name="Fuente Original",
        status="ACTIVE",
    )
    session.add(inst_a)
    await session.flush()

    ver_a = InstrumentVersion(
        instrument_id=inst_a.id,
        version_code="v1.0",
        version_name="Versión Inicial",
        edition="1ra Edición",
        status="ACTIVE",
        scoring_status="CONFIGURED",
    )
    session.add(ver_a)
    await session.flush()

    # Cerrar estudio vinculado
    study_a.instrument_version_id = ver_a.id
    study_a.status = "CLOSED"
    await session.commit()

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Modificar metadato documental sin justificación -> 409 Bloqueado
            res_no_reason = await client.patch(
                f"/api/v1/instruments/{inst_a.id}",
                json={"author": "Autor Modificado Sin Razon"},
                headers=_auth_headers(operator),
            )
            assert res_no_reason.status_code == 409
            assert "EVALUATION_CLOSED_RETROACTIVE_LOCK" in res_no_reason.text

            # 2. Tenant con justificación intenta rectificar -> 403 Sólo operador/admin central
            res_tenant_rect = await client.patch(
                f"/api/v1/instruments/{inst_a.id}",
                json={"author": "Autor Modificado", "rectification_reason": "Corrección de fe de erratas"},
                headers=_auth_headers(user_a),
            )
            assert res_tenant_rect.status_code == 403

            # 3. Operador con justificación válida rectifica metadatos documentales de instrumento -> 200 OK
            res_op_rect = await client.patch(
                f"/api/v1/instruments/{inst_a.id}",
                json={"author": "Autor Rectificado", "source_name": "Nueva Fuente Oficial", "rectification_reason": "Corrección de fe de erratas aprobada por comité"},
                headers=_auth_headers(operator),
            )
            assert res_op_rect.status_code == 200
            assert res_op_rect.json()["author"] == "Autor Rectificado"

            # Verificar que los valores anteriores están preservados en el historial
            inst_db = await session.get(Instrument, inst_a.id)
            await session.refresh(inst_db)
            rects = inst_db.metadata_.get("administrative_rectifications", [])
            assert len(rects) == 1
            assert rects[0]["previous_values"]["author"] == "Autor Original"
            assert rects[0]["new_values"]["author"] == "Autor Rectificado"
            assert rects[0]["reason"] == "Corrección de fe de erratas aprobada por comité"

            # 4. Operador intenta modificar campos estructurales incluso con justificación -> 409 Bloqueo absoluto
            res_struct_tamper = await client.patch(
                f"/api/v1/instruments/{inst_a.id}",
                json={"method_code": "OTRO_METODO", "rectification_reason": "Intento de cambiar metodología cerrada"},
                headers=_auth_headers(operator),
            )
            assert res_struct_tamper.status_code == 409
            assert "EVALUATION_CLOSED_RETROACTIVE_LOCK" in res_struct_tamper.text

            # 5. Rectificación administrativa sobre la versión por el operador
            res_ver_rect = await client.patch(
                f"/api/v1/instrument-versions/{ver_a.id}",
                json={"version_name": "Versión 1.0 (Rectificada)", "rectification_reason": "Clarificación de nomenclatura documental"},
                headers=_auth_headers(operator),
            )
            assert res_ver_rect.status_code == 200
            ver_db = await session.get(InstrumentVersion, ver_a.id)
            await session.refresh(ver_db)
            ver_rects = (ver_db.config or {}).get("administrative_rectifications", [])
            assert len(ver_rects) == 1
            assert ver_rects[0]["previous_values"]["version_name"] == "Versión Inicial"

            # 6. Intento de modificar scoring o reglas metodológicas de versión cerrada -> 409
            res_rules_tamper = await client.patch(
                f"/api/v1/instrument-versions/{ver_a.id}",
                json={"methodological_rules": {"new": "rule"}, "rectification_reason": "Intento alterar baremos cerrados"},
                headers=_auth_headers(operator),
            )
            assert res_rules_tamper.status_code == 409
            assert "EVALUATION_CLOSED_RETROACTIVE_LOCK" in res_rules_tamper.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_12_autenticacion_explicita_elimina_owner_user_id_fallback(session):
    """12. Eliminación de recuperación implícita mediante owner_user_id y exigencia de autenticación explícita (Requisito 4)."""
    user_a, org_a, proj_a, _ = await _setup_company(session, "AlfaNoBypass", "owner-alfa-12@aurora.pe")

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Petición anónima a POST /api/v1/instruments con payload {owner_user_id: user_a.id} debe ser 401
            res_anon_inst = await client.post(
                "/api/v1/instruments",
                json={"name": "Instrumento Hacker", "owner_user_id": user_a.id},
            )
            assert res_anon_inst.status_code == 401, f"Esperado 401, obtenido {res_anon_inst.status_code}"
            assert res_anon_inst.json().get("error_code") == "AUTHENTICATION_ERROR"

            # 2. Petición anónima a POST /api/v1/projects/{proj_id}/instruments debe ser 401
            res_anon_proj_inst = await client.post(
                f"/api/v1/projects/{proj_a.id}/instruments",
                json={"name": "Instrumento Proyecto Hacker", "owner_user_id": user_a.id},
            )
            assert res_anon_proj_inst.status_code == 401
            assert res_anon_proj_inst.json().get("error_code") == "AUTHENTICATION_ERROR"

            # 3. Petición anónima a POST /api/v1/instruments/{id}/versions debe ser 401
            inst_a = Instrument(project_id=proj_a.id, owner_user_id=user_a.id, organization_id=org_a.id, name="Inst Legítimo")
            session.add(inst_a)
            await session.commit()
            await session.refresh(inst_a)

            res_anon_ver = await client.post(
                f"/api/v1/instruments/{inst_a.id}/versions",
                json={"version_code": "v_hack"},
            )
            assert res_anon_ver.status_code == 401
            assert res_anon_ver.json().get("error_code") == "AUTHENTICATION_ERROR"
    finally:
        app.dependency_overrides.clear()

