"""Integration test suite explicitly covering the 8 mandatory PR #10 commercial integrity requirements:
1. Dos empresas distintas (aislamiento multi-tenant).
2. Usuarios con varios roles (Owner, Collaborator, Outsider, Platform Operator).
3. Cotizaciones concurrentes (solicitudes independientes con snapshots aislados).
4. Pago duplicado (rechazo estricto de doble confirmación).
5. Orden vencida (rechazo de reserva para órdenes fuera de vigencia).
6. Cambio de tarifario (inmutabilidad estricta de snapshots previos).
7. Generación fallida (liberación de reserva y preservación de crédito).
8. Consumo simultáneo de una misma licencia (bloqueo atómico y prevención de reutilización).
"""
from datetime import datetime, timedelta, UTC
from decimal import Decimal
import pytest

from app.core.config import get_settings
from app.core.exceptions import AuthorizationError, ConflictError, ValidationDomainError
from app.models.billing import ReportOrder
from app.models.project import Project
from app.models.report import ReportRun
from app.models.study import Study
from app.models.survey import Survey
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.billing import TariffInput
from app.services.billing_service import BillingService
from app.api.v1.reports import _assert_study_access


async def _setup_tenant(session, prefix: str, owner_email: str):
    user = User(email=owner_email, username=prefix.lower(), status="ACTIVE")
    session.add(user)
    await session.flush()
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
    study = Study(project_id=proj.id, survey_id=surv.id, name=f"Study {prefix}", study_type="RESEARCH")
    session.add(study)
    await session.commit()
    return user, org, proj, study


@pytest.mark.asyncio
async def test_01_dos_empresas_distintas(session, seed_user, monkeypatch):
    """Requisito 1: Dos empresas distintas totalmente aisladas comercialmente."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    user_a, org_a, _proj_a, study_a = await _setup_tenant(session, "Alfa", "owner-alfa@aurora.pe")
    user_b, org_b, _proj_b, study_b = await _setup_tenant(session, "Beta", "owner-beta@aurora.pe")

    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=100, price=Decimal("150.00")), seed_user)

    order_a = await service.create_quote(study_a.id, 40, user_a)
    order_b = await service.create_quote(study_b.id, 60, user_b)

    # Empresa A consulta su resumen y sólo ve su orden
    summary_a = await service.get_organization_billing_summary(org_a.id, user_a)
    assert summary_a["organization_id"] == org_a.id
    assert summary_a["total_orders"] == 1
    assert summary_a["orders"][0].id == order_a.id

    # Intento cruzado de Empresa B de ver resumen de Empresa A es bloqueado
    with pytest.raises(AuthorizationError):
        await service.get_organization_billing_summary(org_a.id, user_b)

    # Intento cruzado de Empresa B de consultar informes de Empresa A es bloqueado
    with pytest.raises(AuthorizationError):
        await _assert_study_access(session, study_a.id, user_b)


@pytest.mark.asyncio
async def test_02_usuarios_varios_roles(session, seed_user, monkeypatch):
    """Requisito 2: Usuarios con varios roles (Owner, Colaborador, Outsider, Operador)."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner, org, _proj, study = await _setup_tenant(session, "RolesCorp", "owner-roles@aurora.pe")

    collab = User(email="collab-roles@aurora.pe", username="collab_roles", status="ACTIVE")
    outsider = User(email="outsider-roles@aurora.pe", username="outsider_roles", status="ACTIVE")
    session.add_all([collab, outsider])
    await session.flush()
    session.add(OrganizationMembership(organization_id=org.id, user_id=collab.id, role_code="COLLABORATOR"))
    await session.commit()

    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=50, price=Decimal("120.00")), seed_user)

    # Colaborador NO puede cotizar
    with pytest.raises(AuthorizationError):
        await service.create_quote(study.id, 30, collab)

    # Outsider NO puede cotizar
    with pytest.raises(AuthorizationError):
        await service.create_quote(study.id, 30, outsider)

    # Owner SÍ puede cotizar
    order = await service.create_quote(study.id, 30, owner)
    assert order.status == "PENDING_PAYMENT"

    # Owner NO puede modificar tarifas
    with pytest.raises(AuthorizationError):
        await service.save_tariff(TariffInput(min_workers=1, max_workers=50, price=Decimal("99.00")), owner)

    # Owner NO puede auto-confirmarse pagos
    with pytest.raises(AuthorizationError):
        await service.confirm_payment(order.id, "SELF-PAY-123", owner)

    # Operador SÍ puede confirmar pagos
    confirmed = await service.confirm_payment(order.id, "OP-CONFIRM-123", seed_user)
    assert confirmed.status == "PAID"


@pytest.mark.asyncio
async def test_03_cotizaciones_concurrentes(session, seed_user, monkeypatch):
    """Requisito 3: Cotizaciones concurrentes con trazabilidad y snapshots independientes."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner, _org, _proj, study = await _setup_tenant(session, "ConcurCorp", "owner-concur@aurora.pe")

    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=50, price=Decimal("100.00")), seed_user)
    await service.save_tariff(TariffInput(min_workers=51, max_workers=200, price=Decimal("250.00")), seed_user)

    order1 = await service.create_quote(study.id, 45, owner, headcount_source="ESTUDIO_DECLARADO")
    with pytest.raises(ValidationDomainError, match="planilla oficial verificada"):
        await service.create_quote(study.id, 80, owner, headcount_source="PLANILLA_OFICIAL_EMPRESA")
    order2 = await service.create_quote(study.id, 80, owner, headcount_source="ESTUDIO_DECLARADO")

    assert order1.id != order2.id
    assert order1.workers == 45
    assert order1.amount == Decimal("100.00")
    assert order1.snapshot_data["workers"] == 45
    assert order1.snapshot_data["amount"] == "100.00" or order1.snapshot_data["amount"] == "100"

    assert order2.workers == 80
    assert order2.amount == Decimal("250.00")
    assert order2.snapshot_data["workers"] == 80
    assert order2.snapshot_data["amount"] == "250.00" or order2.snapshot_data["amount"] == "250"


@pytest.mark.asyncio
async def test_04_pago_duplicado(session, seed_user, monkeypatch):
    """Requisito 4: Pago duplicado rechazado estrictamente."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner, _org, _proj, study = await _setup_tenant(session, "DupPayCorp", "owner-duppay@aurora.pe")

    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=50, price=Decimal("100.00")), seed_user)
    order = await service.create_quote(study.id, 30, owner)

    # Primer pago exitoso
    paid = await service.confirm_payment(order.id, "REF-PAGO-ORIGINAL", seed_user)
    assert paid.status == "PAID"

    # Intento de segundo pago sobre la misma orden falla
    with pytest.raises(ConflictError, match="Esta orden ya fue pagada"):
        await service.confirm_payment(order.id, "REF-PAGO-DUPLICADO", seed_user)


@pytest.mark.asyncio
async def test_05_orden_vencida(session, seed_user, monkeypatch):
    """Requisito 5: Orden vencida rechazada de reserva para informe."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner, _org, _proj, study = await _setup_tenant(session, "ExpCorp", "owner-exp@aurora.pe")

    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=50, price=Decimal("100.00")), seed_user)
    order = await service.create_quote(study.id, 30, owner)
    await service.confirm_payment(order.id, "REF-VENCIDA", seed_user)

    # Vencer orden en base de datos
    order.expires_at = datetime.now(UTC) - timedelta(days=3)
    await session.commit()

    monkeypatch.setattr(get_settings(), "environment", "production")
    with pytest.raises(ConflictError, match="ha vencido su per"):
        await service.reserve_report_order(order.id, study.id)


@pytest.mark.asyncio
async def test_06_cambio_tarifario(session, seed_user, monkeypatch):
    """Requisito 6: Cambio de tarifario no altera snapshots ni precios previos."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner, _org, _proj, study = await _setup_tenant(session, "TariffCorp", "owner-tariff@aurora.pe")

    service = BillingService(session)
    tariff = await service.save_tariff(TariffInput(min_workers=1, max_workers=50, price=Decimal("100.00")), seed_user)

    order_old = await service.create_quote(study.id, 30, owner)
    assert order_old.amount == Decimal("100.00")
    assert order_old.snapshot_data["amount"] == "100.00" or order_old.snapshot_data["amount"] == "100"

    # Operador actualiza la tarifa a un precio mayor
    await service.save_tariff(
        TariffInput(min_workers=1, max_workers=50, price=Decimal("180.00")),
        seed_user, tariff_id=tariff.id,
    )

    # La orden previa mantiene su snapshot y monto pactado inalterable
    await session.refresh(order_old)
    assert order_old.amount == Decimal("100.00")
    assert order_old.snapshot_data["amount"] == "100.00" or order_old.snapshot_data["amount"] == "100"

    # Nueva cotización toma el precio nuevo
    order_new = await service.create_quote(study.id, 30, owner)
    assert order_new.amount == Decimal("180.00")
    assert order_new.snapshot_data["amount"] == "180.00" or order_new.snapshot_data["amount"] == "180"


@pytest.mark.asyncio
async def test_07_generacion_fallida(session, seed_user, monkeypatch):
    """Requisito 7: Generación fallida libera la reserva y preserva el crédito."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner, _org, _proj, study = await _setup_tenant(session, "FailCorp", "owner-fail@aurora.pe")

    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=50, price=Decimal("100.00")), seed_user)
    order = await service.create_quote(study.id, 30, owner)
    await service.confirm_payment(order.id, "REF-FAIL-RENDER", seed_user)

    monkeypatch.setattr(get_settings(), "environment", "production")
    reserved = await service.reserve_report_order(order.id, study.id)
    assert reserved.status == "RESERVED"

    # Simulación de falla en LibreOffice / DOCX render
    await service.release_reservation(reserved)
    await session.refresh(reserved)

    assert reserved.status == "PAID"
    assert reserved.consumed_at is None

    # El crédito se preservó y la orden puede ser reservada nuevamente
    re_reserved = await service.reserve_report_order(order.id, study.id)
    assert re_reserved.status == "RESERVED"


@pytest.mark.asyncio
async def test_08_consumo_simultaneo_misma_licencia(session, seed_user, monkeypatch):
    """Requisito 8: Consumo simultáneo o concurrente de una misma licencia bloqueado."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner, _org, _proj, study = await _setup_tenant(session, "LockCorp", "owner-lock@aurora.pe")

    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=50, price=Decimal("100.00")), seed_user)
    order = await service.create_quote(study.id, 30, owner)
    await service.confirm_payment(order.id, "REF-LOCK", seed_user)

    monkeypatch.setattr(get_settings(), "environment", "production")
    # Primera reserva transiciona atómicamente a RESERVED
    res1 = await service.reserve_report_order(order.id, study.id)
    assert res1.status == "RESERVED"

    # Segunda reserva concurrente sobre la misma orden es bloqueada
    with pytest.raises(ConflictError, match="ya se encuentra reservada"):
        await service.reserve_report_order(order.id, study.id)

    # Una vez consumida, tampoco puede reutilizarse
    report = ReportRun(study_id=study.id, billing_order_id=res1.id, output_format="DOCX", status="COMPLETED")
    session.add(report)
    await session.flush()
    await service.consume_order(res1, report.id)
    await session.commit()

    with pytest.raises(ConflictError, match="ya fue utilizada"):
        await service.reserve_report_order(order.id, study.id)



@pytest.mark.asyncio
async def test_manual_quote_snapshot_is_persisted(session, seed_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner, org, _project, study = await _setup_tenant(session, "ManualSnapshot", "manual-snapshot@aurora.pe")
    service = BillingService(session)
    await service.save_tariff(
        TariffInput(min_workers=1, max_workers=100, pricing_mode="QUOTE", price=None),
        seed_user,
    )
    order = await service.create_quote(study.id, 40, owner)
    assert order.snapshot_data["amount"] is None
    await service.set_manual_quote_price(order.id, Decimal("375.00"), seed_user)
    await session.refresh(order)
    assert order.amount == Decimal("375.00")
    assert order.snapshot_data["amount"] == "375.00"
    assert order.snapshot_data["pricing_finalized_at"]


@pytest.mark.asyncio
async def test_expired_paid_order_is_not_an_available_license(session, seed_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner, org, _project, study = await _setup_tenant(session, "ExpiredBalance", "expired-balance@aurora.pe")
    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=100, price=Decimal("120.00")), seed_user)
    order = await service.create_quote(study.id, 40, owner)
    await service.confirm_payment(order.id, "EXPIRED-TXN", seed_user)
    order.expires_at = datetime.now(UTC) - timedelta(days=1)
    await session.commit()
    summary = await service.get_organization_billing_summary(org.id, owner)
    assert summary["available_licenses"] == 0
    assert summary["orders"][0].status == "EXPIRED"
    await session.refresh(order)
    assert order.status == "PAID"  # View does not rewrite the financial audit row.


@pytest.mark.asyncio
async def test_official_source_requires_verified_company_evidence(session, seed_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner, org, _project, study = await _setup_tenant(session, "SourceProof", "source-proof@aurora.pe")
    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=100, price=Decimal("120.00")), seed_user)
    with pytest.raises(ValidationDomainError, match="planilla oficial verificada"):
        await service.create_quote(study.id, 60, owner, headcount_source="PLANILLA_OFICIAL_EMPRESA")
    with pytest.raises(ValidationDomainError, match="auditoría de RR. HH. verificada"):
        await service.create_quote(study.id, 60, owner, headcount_source="AUDITORIA_RRHH")
    with pytest.raises(ValidationDomainError, match="fuente de dotación"):
        await service.create_quote(study.id, 60, owner, headcount_source="FUENTE_FALSA")
    org.metadata_ = {"verified_workers": 75}
    await session.commit()
    with pytest.raises(ValidationDomainError, match="no puede ser menor"):
        await service.create_quote(study.id, 60, owner, headcount_source="PLANILLA_OFICIAL_EMPRESA")
    valid = await service.create_quote(study.id, 75, owner, headcount_source="PLANILLA_OFICIAL_EMPRESA")
    assert valid.workers == 75 and valid.headcount_source == "PLANILLA_OFICIAL_EMPRESA"
