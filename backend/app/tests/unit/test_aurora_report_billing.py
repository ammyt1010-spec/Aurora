"""The enterprise payment model remains safe when tariff prices change."""
from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.core.exceptions import AuthorizationError, ConflictError
from app.models.billing import ReportOrder
from app.models.project import Project
from app.models.report import ReportRun
from app.models.study import Study
from app.models.survey import Survey
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.billing import TariffInput
from app.services.billing_service import BillingService


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
    report = ReportRun(study_id=study.id, billing_order_id=reservation.id,
                       output_format="DOCX", status="COMPLETED")
    session.add(report)
    await session.flush()
    await service.consume_order(reservation, report.id)
    await session.commit()
    assert (await session.get(ReportOrder, order.id)).status == "CONSUMED"
    with pytest.raises(ConflictError):
        await service.reserve_report_order(order.id, study.id)
