"""Operator-only evidence approval, revocation, quote snapshots and tenant isolation."""
import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.core.exceptions import AuthorizationError, ConflictError, ValidationDomainError
from app.models.project import Project
from app.models.study import Study
from app.models.survey import Survey
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.billing import TariffInput
from app.schemas.headcount_evidence import HeadcountEvidenceApprove
from app.services.billing_service import BillingService
from app.services.headcount_evidence_service import HeadcountEvidenceService


def request_payload(value: str, workers: int = 100, days: int = 90, source: str = "PLANILLA_OFICIAL_EMPRESA"):
    return HeadcountEvidenceApprove(
        source_type=source, workers=workers,
        document_sha256=hashlib.sha256(value.encode()).hexdigest(),
        evidence_reference=f"FOLIO-{value}",
        valid_until=datetime.now(UTC) + timedelta(days=days),
    )


async def create_company(session, name, owner):
    org = Organization(name=name, tax_id=f"TAX-{name}")
    session.add(org)
    await session.flush()
    session.add(OrganizationMembership(organization_id=org.id, user_id=owner.id, role_code="OWNER"))
    project = Project(owner_user_id=owner.id, organization_id=org.id, name="Prueba de dotación", project_type="RESEARCH")
    session.add(project)
    await session.flush()
    survey = Survey(project_id=project.id, created_by_user_id=owner.id, name="Encuesta", survey_type="CUSTOM")
    session.add(survey)
    await session.flush()
    study = Study(project_id=project.id, survey_id=survey.id, name="Estudio de dotación", study_type="RESEARCH")
    session.add(study)
    await session.commit()
    return org, study


@pytest.mark.asyncio
async def test_operator_only_versioned_headcount_and_snapshot(session, seed_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner = User(email="evidence-owner@aurora.test", username="evidence-owner", status="ACTIVE")
    outsider = User(email="evidence-outsider@aurora.test", username="evidence-outsider", status="ACTIVE")
    session.add_all([owner, outsider])
    await session.flush()
    org, study = await create_company(session, "EvidenceCo", owner)
    svc = HeadcountEvidenceService(session)

    with pytest.raises(AuthorizationError):
        await svc.approve(org.id, request_payload("v1"), owner)
    with pytest.raises(AuthorizationError):
        await svc.list_history(org.id, outsider)

    first = await svc.approve(org.id, request_payload("v1", workers=100), seed_user)
    assert first.id
    assert len(await svc.list_history(org.id, owner)) == 1
    with pytest.raises(ConflictError):
        await svc.approve(org.id, request_payload("v1"), seed_user)

    billing = BillingService(session)
    await billing.save_tariff(TariffInput(min_workers=1, max_workers=100, price=Decimal("120.00")), seed_user)
    await billing.save_tariff(TariffInput(min_workers=101, max_workers=250, price=Decimal("230.00")), seed_user)
    with pytest.raises(ValidationDomainError, match="no puede ser menor"):
        await billing.create_quote(study.id, 75, owner, headcount_source="PLANILLA_OFICIAL_EMPRESA")
    quote = await billing.create_quote(study.id, 100, owner, headcount_source="PLANILLA_OFICIAL_EMPRESA")
    assert quote.snapshot_data["headcount_evidence"]["id"] == first.id
    assert quote.snapshot_data["headcount_evidence"]["sha256"] == first.document_sha256

    updated = await svc.approve(org.id, request_payload("v2", workers=150), seed_user)
    await session.refresh(first)
    assert first.revoked_at is not None
    with pytest.raises(ValidationDomainError, match="no puede ser menor"):
        await billing.create_quote(study.id, 100, owner, headcount_source="PLANILLA_OFICIAL_EMPRESA")
    quote2 = await billing.create_quote(study.id, 150, owner, headcount_source="PLANILLA_OFICIAL_EMPRESA")
    assert quote2.snapshot_data["headcount_evidence"]["id"] == updated.id
    await session.refresh(quote)
    assert quote.snapshot_data["headcount_evidence"]["id"] == first.id

    with pytest.raises(AuthorizationError):
        await svc.revoke(org.id, updated.id, owner)
    revoked = await svc.revoke(org.id, updated.id, seed_user)
    assert revoked.revoked_at
    monkeypatch.setattr(get_settings(), "environment", "staging")
    with pytest.raises(ValidationDomainError, match="verificación documentada"):
        await billing.create_quote(study.id, 150, owner, headcount_source="PLANILLA_OFICIAL_EMPRESA")


@pytest.mark.asyncio
async def test_expiring_evidence_cannot_certify_new_production_quote(session, seed_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    owner = User(email="evidence-expiry@aurora.test", username="evidence-expiry", status="ACTIVE")
    session.add(owner)
    await session.flush()
    org, study = await create_company(session, "ExpiryCo", owner)
    svc = HeadcountEvidenceService(session)
    record = await svc.approve(org.id, request_payload("expiry", 90), seed_user)
    record.verified_at = datetime.now(UTC) - timedelta(days=365)
    record.valid_until = datetime.now(UTC) - timedelta(days=1)
    await session.commit()
    monkeypatch.setattr(get_settings(), "environment", "staging")
    billing = BillingService(session)
    with pytest.raises(ValidationDomainError, match="verificación documentada"):
        await billing.create_quote(study.id, 90, owner, headcount_source="PLANILLA_OFICIAL_EMPRESA")
