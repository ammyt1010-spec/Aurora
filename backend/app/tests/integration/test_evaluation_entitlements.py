"""Cupo empresarial: cuatro aplicaciones gratuitas y una emisión por uso."""

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.billing import ReportOrder, ReportTariff
from app.models.evaluation_entitlement import EvaluationEntitlement
from app.models.study import Study, StudySnapshot
from app.models.user import Organization, User
from app.services.billing_service import BillingService
from app.services.evaluation_access_service import EvaluationAccessService
from app.tests.integration.test_censopas_flow import _setup_censopas_study


@pytest.mark.asyncio
async def test_free_counter_is_shared_by_all_instruments(session, seed_user, seed_project):
    studies = [
        Study(project_id=seed_project.id, survey_id=100 + index, name=f"Aplicación {index}", study_type="CENSO")
        for index in range(4)
    ]
    session.add_all(studies)
    await session.flush()
    session.add_all([
        EvaluationEntitlement(user_id=seed_user.id, study_id=study.id, access_kind="FREE", status="ACTIVE")
        for study in studies
    ])
    await session.commit()

    status = await EvaluationAccessService(session).trial_status(seed_user.id)
    assert status == {"limit": 4, "used": 4, "remaining": 0}


@pytest.mark.asyncio
async def test_free_evaluation_emits_only_one_full_report(
    client: AsyncClient, session, seed_user, seed_project,
):
    client.headers["Authorization"] = f"Bearer {create_access_token(seed_user.id)}"
    study, _ = await _setup_censopas_study(client, seed_user, seed_project, min_publishable_n=1)
    session.add(EvaluationEntitlement(
        user_id=seed_user.id, study_id=study["id"], access_kind="FREE", status="ACTIVE",
    ))
    await session.commit()

    first = await client.post(
        f"/api/v1/studies/{study['id']}/reports",
        json={"output_format": "DOCX", "report_mode": "PROVISIONAL"},
    )
    assert first.status_code == 201, first.text
    downloaded = await client.get(f"/api/v1/reports/{first.json()['id']}/download")
    assert downloaded.status_code == 200

    second = await client.post(
        f"/api/v1/studies/{study['id']}/reports",
        json={"output_format": "DOCX", "report_mode": "PROVISIONAL"},
    )
    assert second.status_code == 409
    entitlement = (await session.execute(
        select(EvaluationEntitlement).where(EvaluationEntitlement.study_id == study["id"])
    )).scalar_one()
    await session.refresh(entitlement)
    assert entitlement.free_report_id == first.json()["id"]


@pytest.mark.asyncio
async def test_pending_payment_study_has_no_public_link(
    client: AsyncClient, session, seed_user, seed_project,
):
    client.headers["Authorization"] = f"Bearer {create_access_token(seed_user.id)}"
    study, _ = await _setup_censopas_study(client, seed_user, seed_project, min_publishable_n=1)
    session.add(EvaluationEntitlement(
        user_id=seed_user.id, study_id=study["id"], access_kind="PAID", status="PENDING_PAYMENT",
    ))
    await session.commit()
    access = await client.get(f"/api/v1/quick-eval/studies/{study['id']}/access")
    assert access.status_code == 200
    assert access.json()["survey_url"] is None


@pytest.mark.asyncio
async def test_operator_issues_one_company_credential_per_ruc(client, session, seed_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    payload = {
        "email": "empresa-nueva@example.com",
        "username": "empresa_nueva",
        "initial_password": "ClaveSegura!2026",
        "company_name": "Empresa Nueva SAC",
        "company_ruc": "20123456780",
        "company_workers": 250,
    }
    unauthorized = await client.post("/api/v1/auth/company-accounts", json=payload)
    assert unauthorized.status_code == 401
    client.headers["Authorization"] = f"Bearer {create_access_token(seed_user.id)}"
    created = await client.post("/api/v1/auth/company-accounts", json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["free_evaluations"] == 4
    assert "initial_password" not in created.json()
    user = await session.get(User, created.json()["user_id"])
    company = await session.get(Organization, created.json()["organization_id"])
    await session.refresh(user)
    assert user.metadata_["managed_company_id"] == company.id
    assert user.managed_company_id == company.id
    assert company.metadata_["headcount"] == 250
    duplicate = await client.post("/api/v1/auth/company-accounts", json={
        **payload, "email": "otra@example.com", "username": "otra_empresa",
    })
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_public_signup_is_closed_outside_test_environment(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "development")
    policy = await client.get("/api/v1/auth/registration-policy")
    assert policy.json()["self_registration_enabled"] is False
    signup = await client.post("/api/v1/auth/register", json={
        "email": "libre@example.com", "username": "libre", "password": "ClaveSegura!2026",
    })
    assert signup.status_code == 403


@pytest.mark.asyncio
async def test_company_self_signup_creates_one_managed_account(client, session, monkeypatch):
    monkeypatch.setattr(get_settings(), "self_registration_enabled", True)
    payload = {
        "email": "Gerencia@Ejemplo.com", "username": "gerencia_ejemplo",
        "password": "ClaveSegura!2026", "company_name": "Empresa Ejemplo SAC",
        "company_ruc": "20612345678", "company_workers": 240,
    }
    created = await client.post("/api/v1/auth/company-signup", json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["email"] == "gerencia@ejemplo.com"
    assert created.json()["free_evaluations"] == 4
    user = await session.get(User, created.json()["user_id"])
    assert user.managed_company_id == created.json()["organization_id"]
    duplicate = await client.post("/api/v1/auth/company-signup", json={
        **payload, "email": "otra@ejemplo.com", "username": "otra_ejemplo",
    })
    assert duplicate.status_code == 409
    login = await client.post("/api/v1/auth/login", json={
        "email": "gerencia@ejemplo.com", "password": payload["password"],
    })
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_public_signup_requires_email_confirmation_before_login(client, session, monkeypatch):
    from app.services import company_account_service, company_email_service
    from app.services.company_email_service import confirmation_token

    settings = get_settings()
    monkeypatch.setattr(settings, "self_registration_enabled", True)
    monkeypatch.setattr(settings, "email_verification_required", True)
    sent = []

    async def capture_confirmation(user, company_name):
        sent.append((user.email, company_name, confirmation_token(user)))

    monkeypatch.setattr(company_account_service, "send_confirmation", capture_confirmation)
    monkeypatch.setattr(company_email_service, "send_confirmation", capture_confirmation)
    payload = {
        "email": "confirmacion@ejemplo.com", "username": "empresa_confirmacion",
        "password": "ClaveSegura!2026", "company_name": "Empresa Confirmación SAC",
        "company_ruc": "20612345670", "company_workers": 250,
    }
    created = await client.post("/api/v1/auth/company-signup", json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["verification_required"] is True
    assert len(sent) == 1
    user = await session.get(User, created.json()["user_id"])
    assert user.status == "PENDING_EMAIL"
    assert len(user.metadata_["email_verification_sent_at"]) == 1
    assert (await client.post("/api/v1/auth/resend-company-verification", json={"email": payload["email"]})).status_code == 204
    assert len(sent) == 1  # Too soon: resend cooldown is server-side.
    user.metadata_ = {
        **user.metadata_,
        "email_verification_sent_at": [(datetime.now(UTC) - timedelta(seconds=61)).isoformat()],
    }
    await session.commit()
    assert (await client.post("/api/v1/auth/resend-company-verification", json={"email": payload["email"]})).status_code == 204
    assert len(sent) == 2
    login_payload = {"email": payload["email"], "password": payload["password"]}
    assert (await client.post("/api/v1/auth/login", json=login_payload)).status_code == 401
    confirmed = await client.post("/api/v1/auth/verify-company-email", json={"token": sent[0][2]})
    assert confirmed.status_code == 204, confirmed.text
    assert (await client.post("/api/v1/auth/verify-company-email", json={"token": sent[0][2]})).status_code == 401
    assert (await client.post("/api/v1/auth/login", json=login_payload)).status_code == 200


@pytest.mark.asyncio
async def test_operator_can_list_suspend_and_reset_managed_account(client, session, seed_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    payload = {
        "email": "operaciones@ejemplo.com", "username": "operaciones_ejemplo",
        "initial_password": "ClaveSegura!2026", "company_name": "Operaciones Ejemplo SAC",
        "company_ruc": "20612345679", "company_workers": 250,
    }
    assert (await client.get("/api/v1/auth/company-accounts")).status_code == 401
    client.headers["Authorization"] = f"Bearer {create_access_token(seed_user.id)}"
    created = await client.post("/api/v1/auth/company-accounts", json=payload)
    assert created.status_code == 201, created.text
    user_id = created.json()["user_id"]
    accounts = await client.get("/api/v1/auth/company-accounts", params={"q": "Operaciones Ejemplo"})
    assert accounts.status_code == 200
    assert accounts.json()["total"] == 1
    assert accounts.json()["items"][0]["free_remaining"] == 4
    original_token = create_access_token(user_id)
    suspended = await client.patch(f"/api/v1/auth/company-accounts/{user_id}/status", json={"status": "SUSPENDED"})
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "SUSPENDED"
    client.headers["Authorization"] = f"Bearer {original_token}"
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    client.headers["Authorization"] = f"Bearer {create_access_token(seed_user.id)}"
    reactivated = await client.patch(f"/api/v1/auth/company-accounts/{user_id}/status", json={"status": "ACTIVE"})
    assert reactivated.status_code == 200
    reset = await client.post(f"/api/v1/auth/company-accounts/{user_id}/reset-password", json={
        "new_password": "ClaveNueva!2026",
    })
    assert reset.status_code == 204
    client.headers.pop("Authorization")
    old_login = await client.post("/api/v1/auth/login", json={
        "email": payload["email"], "password": payload["initial_password"],
    })
    assert old_login.status_code == 401
    new_login = await client.post("/api/v1/auth/login", json={
        "email": payload["email"], "password": "ClaveNueva!2026",
    })
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_company_credentials_cannot_create_study_for_another_ruc(client, session, seed_user, seed_project):
    seed_user.metadata_ = {"managed_company_id": seed_project.organization_id}
    await session.commit()
    client.headers["Authorization"] = f"Bearer {create_access_token(seed_user.id)}"
    response = await client.post("/api/v1/quick-eval", json={
        "company_name": "Otra Empresa SAC", "company_ruc": "20987654321",
        "instrument_version": "SHORT", "study_name": "Intento de otra empresa",
        "population_invited": 25,
    })
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_provisional_bank_details_never_invite_transfer(client, seed_user, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "payment_bank_name", "Banco por definir")
    monkeypatch.setattr(settings, "payment_account_holder", "AURORA (datos provisionales)")
    monkeypatch.setattr(settings, "payment_account_number", "PENDIENTE_DE_CONFIGURAR")
    monkeypatch.setattr(settings, "payment_cci", "PENDIENTE_DE_CONFIGURAR")
    client.headers["Authorization"] = f"Bearer {create_access_token(seed_user.id)}"
    response = await client.get("/api/v1/billing/payment-instructions")
    assert response.status_code == 200
    assert response.json()["provisional"] is True
    assert "no realices una transferencia" in response.json()["notice"]


@pytest.mark.asyncio
async def test_verified_payment_opens_pending_evaluation(client, session, seed_user, seed_project, monkeypatch):
    client.headers["Authorization"] = f"Bearer {create_access_token(seed_user.id)}"
    study_data, _ = await _setup_censopas_study(
        client, seed_user, seed_project, min_publishable_n=1, create_sessions=False,
    )
    study = await session.get(Study, study_data["id"])
    study.status = "DRAFT"
    await session.execute(delete(StudySnapshot).where(StudySnapshot.study_id == study.id))
    tariff = ReportTariff(
        method_code="CENSOPAS_CORTA", pricing_mode="FIXED", min_workers=1,
        max_workers=100, price=Decimal("400.00"), currency="PEN", active=True,
        updated_by_user_id=seed_user.id,
    )
    session.add(tariff)
    await session.flush()
    order = ReportOrder(
        study_id=study.id, organization_id=seed_project.organization_id,
        tariff_id=tariff.id, requested_by_user_id=seed_user.id,
        method_code="CENSOPAS_CORTA", pricing_mode="FIXED", workers=50,
        tariff_min_workers=1, tariff_max_workers=100,
        amount=Decimal("400.00"), currency="PEN", status="PENDING_PAYMENT",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    session.add(order)
    await session.flush()
    entitlement = EvaluationEntitlement(
        user_id=seed_user.id, study_id=study.id, access_kind="PAID",
        status="PENDING_PAYMENT", order_id=order.id,
    )
    session.add(entitlement)
    await session.commit()
    before = await client.get(f"/api/v1/quick-eval/studies/{study.id}/access")
    assert before.json()["survey_url"] is None
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", seed_user.id)
    confirmed = await BillingService(session).confirm_payment(order.id, "TRANSFERENCIA-VERIFICADA-1", seed_user)
    assert confirmed.status == "PAID"
    after = await client.get(f"/api/v1/quick-eval/studies/{study.id}/access")
    assert after.status_code == 200, after.text
    assert after.json()["status"] == "ACTIVE"
    assert after.json()["survey_url"].startswith("/encuesta/")
