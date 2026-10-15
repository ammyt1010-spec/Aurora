"""AURORA initial WEB prices: exact 20% discount, manual quote and method isolation."""
from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ValidationDomainError
from app.core.report_pricing import REFERENCE_WEB_TARIFFS
from app.models.instrument import Instrument, InstrumentVersion
from app.models.project import Project
from app.models.study import Study
from app.models.survey import Survey
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.billing import TariffInput
from app.services.billing_service import BillingService

REFERENCE_PRICES = {
    "SUSESO_ISTAS21_BREVE": [Decimal(x) for x in (200, 300, 400, 500, 700)],
    "CENSOPAS_CORTA": [Decimal(x) for x in (500, 750, 900, 1250)],
    "CENSOPAS_MEDIA": [Decimal(x) for x in (700, 1150, 1500, 1950)],
}


def test_all_web_reference_prices_have_exact_20_percent_discount():
    assert len(REFERENCE_WEB_TARIFFS) == 16
    for method, prices in REFERENCE_PRICES.items():
        actual = [
            Decimal(value)
            for code, low, high, value in REFERENCE_WEB_TARIFFS
            if code == method and value is not None
        ]
        assert actual == [price * Decimal("0.80") for price in prices]
    quote_bands = [(method, start) for method, start, _, price in REFERENCE_WEB_TARIFFS if price is None]
    assert quote_bands == [
        ("SUSESO_ISTAS21_BREVE", 2000),
        ("CENSOPAS_CORTA", 1000),
        ("CENSOPAS_MEDIA", 1000),
    ]


def test_quote_type_must_not_fake_a_fixed_price():
    with pytest.raises(ValueError):
        TariffInput(pricing_mode="QUOTE", min_workers=1000, price=Decimal("5"))
    with pytest.raises(ValueError):
        TariffInput(pricing_mode="FIXED", min_workers=1, price=None)
    with pytest.raises(ValueError):
        TariffInput(pricing_mode="FIXED", min_workers=200, max_workers=100, price=Decimal("200"))


@pytest.mark.asyncio
async def test_quote_censopas_correct_method_and_manual_pricing(session, seed_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    admin = User(email="quote-client@aurora.test", username="quote-client", status="ACTIVE")
    session.add(admin)
    await session.flush()
    org = Organization(name="Censopas Company", tax_id="20110022001")
    session.add(org)
    await session.flush()
    session.add(OrganizationMembership(
        organization_id=org.id, user_id=admin.id, role_code="OWNER", permissions={}
    ))
    project = Project(owner_user_id=admin.id, organization_id=org.id,
                      name="Estudio psicosocial", project_type="CENSO", status="DRAFT")
    session.add(project)
    instrument = Instrument(code="CENSOPAS_COPSOQ", name="CENSOPAS", is_system=True)
    session.add(instrument)
    await session.flush()
    version = InstrumentVersion(
        instrument_id=instrument.id, version_code="SHORT", status="ACTIVE",
        config={"censopas_version_kind": "SHORT"},
    )
    session.add(version)
    await session.flush()
    survey = Survey(
        project_id=project.id, created_by_user_id=admin.id,
        name="Encuesta", survey_type="CUSTOM", status="DRAFT",
    )
    session.add(survey)
    await session.flush()
    study = Study(
        project_id=project.id, survey_id=survey.id,
        instrument_version_id=version.id, name="Evaluación",
        study_type="CENSO", status="CLOSED",
    )
    session.add(study)
    await session.commit()

    service = BillingService(session)
    tariffs = await service.load_reference_tariffs(seed_user)
    assert len(tariffs) == 16
    with pytest.raises(ConflictError):
        await service.load_reference_tariffs(seed_user)
    with pytest.raises(ValidationDomainError):
        await service.create_quote(study.id, 100, admin, method_code="SUSESO_ISTAS21_BREVE")

    fixed = await service.create_quote(study.id, 100, admin, method_code="CENSOPAS_CORTA")
    assert fixed.amount == Decimal("400.00")
    assert fixed.status == "PENDING_PAYMENT"

    manual = await service.create_quote(study.id, 1500, admin, method_code="CENSOPAS_CORTA")
    assert manual.amount is None
    assert manual.status == "AWAITING_QUOTE"
    await service.set_manual_quote_price(manual.id, Decimal("2990.00"), seed_user)
    await session.refresh(manual)
    assert manual.amount == Decimal("2990.00")
    assert manual.status == "PENDING_PAYMENT"

    await service.save_tariff(
        TariffInput(method_code="CENSOPAS_CORTA", min_workers=1, max_workers=100,
                    price=Decimal("425"), currency="PEN"),
        seed_user, tariff_id=next(
            row.id for row in tariffs if row.method_code == "CENSOPAS_CORTA" and row.min_workers == 1
        ),
    )
    await session.refresh(fixed)
    assert fixed.amount == Decimal("400.00")
