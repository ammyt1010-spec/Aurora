"""The enterprise payment model remains safe when tariff prices change,
headcount is verified, concurrent requests are isolated, and tunnels are secured."""
from decimal import Decimal

import pytest
from starlette.requests import Request

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


def build_mock_request(client_ip="127.0.0.1", headers=None, host="127.0.0.1:8003"):
    hdr_list = [(b"host", host.encode())]
    if headers:
        for k, v in headers.items():
            hdr_list.append((k.lower().encode(), v.encode()))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/studies/1/reports",
        "headers": hdr_list,
        "client": (client_ip, 50000),
        "server": ("127.0.0.1", 8003),
        "scheme": "http",
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_company_payment_and_tariff_snapshot(session, seed_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    admin = User(email="company-admin@aurora.test", username="company-admin", status="ACTIVE")
    outsider = User(email="outsider@aurora.test", username="company-outsider", status="ACTIVE")
    session.add_all([admin, outsider])
    await session.flush()
    company = Organization(name="Empresa piloto", tax_id="20600123450")
    session.add(company)
    await session.flush()
    session.add(OrganizationMembership(
        organization_id=company.id, user_id=admin.id, role_code="OWNER", permissions={}
    ))
    project = Project(owner_user_id=admin.id, organization_id=company.id,
                      name="Evaluación piloto", project_type="RESEARCH", status="DRAFT")
    session.add(project)
    await session.flush()
    survey = Survey(project_id=project.id, created_by_user_id=admin.id,
                    name="Encuesta", survey_type="CUSTOM", status="DRAFT")
    session.add(survey)
    await session.flush()
    study = Study(project_id=project.id, survey_id=survey.id,
                  name="Evaluación", study_type="RESEARCH", status="CLOSED")
    session.add(study)
    await session.commit()

    service = BillingService(session)
    with pytest.raises(AuthorizationError):
        await service.save_tariff(TariffInput(min_workers=1, max_workers=49, price=Decimal("100")), admin)
    first = await service.save_tariff(
        TariffInput(min_workers=1, max_workers=49, price=Decimal("100")), seed_user
    )
    await service.save_tariff(
        TariffInput(min_workers=50, max_workers=None, price=Decimal("200")), seed_user
    )
    with pytest.raises(ConflictError):
        await service.save_tariff(
            TariffInput(min_workers=49, max_workers=51, price=Decimal("150")), seed_user
        )
    with pytest.raises(AuthorizationError):
        await service.create_quote(study.id, 20, outsider)

    order = await service.create_quote(study.id, 20, admin)
    assert order.amount == Decimal("100")
    assert order.workers == 20
    assert order.status == "PENDING_PAYMENT"

    await service.save_tariff(
        TariffInput(min_workers=1, max_workers=49, price=Decimal("130")),
        seed_user, tariff_id=first.id,
    )
    await session.refresh(order)
    assert order.amount == Decimal("100")
    new_order = await service.create_quote(study.id, 20, admin)
    assert new_order.amount == Decimal("130")

    with pytest.raises(AuthorizationError):
        await service.confirm_payment(order.id, "TRANSFER-123", admin)
    await service.confirm_payment(order.id, "TRANSFER-123", seed_user)
    with pytest.raises(ConflictError):
        await service.confirm_payment(order.id, "TRANSFER-123", seed_user)

    monkeypatch.setattr(get_settings(), "environment", "production")
    with pytest.raises(ConflictError):
        await service.reserve_report_order(None, study.id)
    reservation = await service.reserve_report_order(order.id, study.id)
    assert reservation.status == "RESERVED"

    # Concurrent reservation on already reserved order fails
    with pytest.raises(ConflictError):
        await service.reserve_report_order(order.id, study.id)

    report = ReportRun(study_id=study.id, billing_order_id=reservation.id,
                       output_format="DOCX", status="COMPLETED")
    session.add(report)
    await session.flush()
    await service.consume_order(reservation, report.id)
    await session.commit()
    assert (await session.get(ReportOrder, order.id)).status == "CONSUMED"
    with pytest.raises(ConflictError):
        await service.reserve_report_order(order.id, study.id)


@pytest.mark.asyncio
async def test_headcount_source_and_anti_reduction(session, seed_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    admin = User(email="hc-admin@aurora.test", username="hc-admin", status="ACTIVE")
    session.add(admin)
    await session.flush()
    company = Organization(
        name="Empresa con Dotación",
        tax_id="20700987654",
        metadata_={"headcount": 100, "verified_workers": 100},
    )
    session.add(company)
    await session.flush()
    session.add(OrganizationMembership(
        organization_id=company.id, user_id=admin.id, role_code="ADMIN", permissions={}
    ))
    project = Project(owner_user_id=admin.id, organization_id=company.id,
                      name="Proyecto Dotación", project_type="RESEARCH", status="ACTIVE")
    session.add(project)
    await session.flush()
    survey = Survey(project_id=project.id, created_by_user_id=admin.id,
                    name="Encuesta Dotación", survey_type="CUSTOM", status="DRAFT")
    session.add(survey)
    await session.flush()
    study = Study(project_id=project.id, survey_id=survey.id,
                  name="Estudio Dotación", study_type="RESEARCH", status="OPEN",
                  settings={"headcount": 100, "headcount_source": "PLANILLA_OFICIAL_EMPRESA"})
    session.add(study)
    await session.commit()

    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=50, price=Decimal("100")), seed_user)
    await service.save_tariff(TariffInput(min_workers=51, max_workers=150, price=Decimal("250")), seed_user)

    # Attempt to unilaterally reduce headcount below company/study official workforce fails
    with pytest.raises(ValidationDomainError, match="no puede ser menor a la dotación"):
        await service.create_quote(study.id, 50, admin)

    # Valid quotation at or above verified workforce succeeds
    order = await service.create_quote(study.id, 100, admin, headcount_source="PLANILLA_OFICIAL_EMPRESA")
    assert order.workers == 100
    assert order.headcount_source == "PLANILLA_OFICIAL_EMPRESA"
    assert order.amount == Decimal("250")

    # Snapshot data is populated with immutable details
    assert order.snapshot_data is not None
    assert order.snapshot_data["workers"] == 100
    assert order.snapshot_data["headcount_source"] == "PLANILLA_OFICIAL_EMPRESA"
    assert order.snapshot_data["organization"]["id"] == company.id
    assert order.snapshot_data["amount"] == "250.00" or order.snapshot_data["amount"] == "250"


@pytest.mark.asyncio
async def test_release_reservation_preserves_entitlement(session, seed_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    admin = User(email="release-admin@aurora.test", username="release-admin", status="ACTIVE")
    session.add(admin)
    await session.flush()
    company = Organization(name="Empresa Release", tax_id="20700987655")
    session.add(company)
    await session.flush()
    session.add(OrganizationMembership(organization_id=company.id, user_id=admin.id, role_code="OWNER"))
    project = Project(owner_user_id=admin.id, organization_id=company.id, name="Prj Release", project_type="RESEARCH")
    session.add(project)
    await session.flush()
    survey = Survey(project_id=project.id, created_by_user_id=admin.id, name="Surv Release", survey_type="CUSTOM")
    session.add(survey)
    await session.flush()
    study = Study(project_id=project.id, survey_id=survey.id, name="Std Release", study_type="RESEARCH")
    session.add(study)
    await session.commit()

    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=50, price=Decimal("150")), seed_user)
    order = await service.create_quote(study.id, 30, admin)
    await service.confirm_payment(order.id, "TX-RELEASE-1", seed_user)

    monkeypatch.setattr(get_settings(), "environment", "production")
    reserved = await service.reserve_report_order(order.id, study.id)
    assert reserved.status == "RESERVED"

    # Simulate render failure releasing reservation
    await service.release_reservation(reserved)
    await session.refresh(reserved)
    assert reserved.status == "PAID"
    assert reserved.consumed_at is None

    # Order can be re-reserved without double payment
    re_reserved = await service.reserve_report_order(order.id, study.id)
    assert re_reserved.status == "RESERVED"


@pytest.mark.asyncio
async def test_public_tunnel_suppresses_license_bypass(session, seed_user, monkeypatch):
    """In non-production, a public tunnel request must require a valid paid license."""
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    monkeypatch.setattr(get_settings(), "environment", "development")

    admin = User(email="tunnel-admin@aurora.test", username="tunnel-admin", status="ACTIVE")
    session.add(admin)
    await session.flush()
    company = Organization(name="Empresa Tunnel", tax_id="20700987656")
    session.add(company)
    await session.flush()
    session.add(OrganizationMembership(organization_id=company.id, user_id=admin.id, role_code="OWNER"))
    project = Project(owner_user_id=admin.id, organization_id=company.id, name="Prj Tunnel", project_type="RESEARCH")
    session.add(project)
    await session.flush()
    survey = Survey(project_id=project.id, created_by_user_id=admin.id, name="Surv Tunnel", survey_type="CUSTOM")
    session.add(survey)
    await session.flush()
    study = Study(project_id=project.id, survey_id=survey.id, name="Std Tunnel", study_type="RESEARCH")
    session.add(study)
    await session.commit()

    service = BillingService(session)

    # Clean direct local request in dev can bypass
    local_req = build_mock_request(client_ip="127.0.0.1")
    assert await service.reserve_report_order(None, study.id, request=local_req) is None

    # Request via public tunnel (CF-Connecting-IP / X-Forwarded-For) CANNOT bypass
    tunnel_req = build_mock_request(
        client_ip="127.0.0.1",
        headers={"cf-connecting-ip": "198.51.100.24", "x-forwarded-for": "198.51.100.24"},
    )
    with pytest.raises(ConflictError, match="solicita una cotizaci"):
        await service.reserve_report_order(None, study.id, request=tunnel_req)


@pytest.mark.asyncio
async def test_enterprise_billing_summary_and_tenant_isolation(session, seed_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner_a = User(email="owner-a@aurora.test", username="owner-a", status="ACTIVE")
    owner_b = User(email="owner-b@aurora.test", username="owner-b", status="ACTIVE")
    session.add_all([owner_a, owner_b])
    await session.flush()

    company_a = Organization(name="Empresa A", tax_id="20100000001")
    company_b = Organization(name="Empresa B", tax_id="20100000002")
    session.add_all([company_a, company_b])
    await session.flush()

    session.add(OrganizationMembership(organization_id=company_a.id, user_id=owner_a.id, role_code="OWNER"))
    session.add(OrganizationMembership(organization_id=company_b.id, user_id=owner_b.id, role_code="OWNER"))

    proj_a = Project(owner_user_id=owner_a.id, organization_id=company_a.id, name="Proj A", project_type="RESEARCH")
    session.add(proj_a)
    await session.flush()
    surv_a = Survey(project_id=proj_a.id, created_by_user_id=owner_a.id, name="Surv A", survey_type="CUSTOM")
    session.add(surv_a)
    await session.flush()
    study_a = Study(project_id=proj_a.id, survey_id=surv_a.id, name="Study A", study_type="RESEARCH")
    session.add(study_a)
    await session.commit()

    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=50, price=Decimal("120")), seed_user)

    order_a1 = await service.create_quote(study_a.id, 25, owner_a)
    await service.confirm_payment(order_a1.id, "TX-A1", seed_user)
    _order_a2 = await service.create_quote(study_a.id, 35, owner_a)

    # Owner A gets their summary with 1 available and 1 pending
    summary_a = await service.get_organization_billing_summary(company_a.id, owner_a)
    assert summary_a["organization_id"] == company_a.id
    assert summary_a["total_orders"] == 2
    assert summary_a["available_licenses"] == 1
    assert summary_a["pending_payment"] == 1
    assert summary_a["consumed_licenses"] == 0

    # Cross-tenant access: Owner B CANNOT access summary of Company A
    with pytest.raises(AuthorizationError):
        await service.get_organization_billing_summary(company_a.id, owner_b)

    # Platform operator can inspect summary of Company A
    summary_op = await service.get_organization_billing_summary(company_a.id, seed_user)
    assert summary_op["total_orders"] == 2

    # Cross-tenant access to study A report downloads
    with pytest.raises(AuthorizationError):
        await _assert_study_access(session, study_a.id, owner_b)

    # Owner A has access to study A
    study_res, proj_res = await _assert_study_access(session, study_a.id, owner_a)
    assert study_res.id == study_a.id
    assert proj_res.id == proj_a.id


@pytest.mark.asyncio
async def test_expired_order_cannot_be_reserved(session, seed_user, monkeypatch):
    """An expired order must be rejected from reservation, preventing stale consumption."""
    from datetime import datetime, timedelta, UTC

    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    admin = User(email="exp-admin@aurora.test", username="exp-admin", status="ACTIVE")
    session.add(admin)
    await session.flush()
    company = Organization(name="Empresa Exp", tax_id="20700987699")
    session.add(company)
    await session.flush()
    session.add(OrganizationMembership(organization_id=company.id, user_id=admin.id, role_code="OWNER"))
    project = Project(owner_user_id=admin.id, organization_id=company.id, name="Prj Exp", project_type="RESEARCH")
    session.add(project)
    await session.flush()
    survey = Survey(project_id=project.id, created_by_user_id=admin.id, name="Surv Exp", survey_type="CUSTOM")
    session.add(survey)
    await session.flush()
    study = Study(project_id=project.id, survey_id=survey.id, name="Std Exp", study_type="RESEARCH")
    session.add(study)
    await session.commit()

    service = BillingService(session)
    await service.save_tariff(TariffInput(min_workers=1, max_workers=50, price=Decimal("150")), seed_user)
    order = await service.create_quote(study.id, 25, admin)
    await service.confirm_payment(order.id, "TX-EXP-1", seed_user)

    # Expire order in the past
    order.expires_at = datetime.now(UTC) - timedelta(days=2)
    await session.commit()

    monkeypatch.setattr(get_settings(), "environment", "production")
    with pytest.raises(ConflictError, match="ha vencido su per"):
        await service.reserve_report_order(order.id, study.id)

