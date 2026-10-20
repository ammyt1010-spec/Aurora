from datetime import UTC, datetime
from unittest.mock import AsyncMock

from httpx import AsyncClient
import pytest

from app.core.exceptions import ConflictError
from app.core.security import create_access_token
from app.schemas.projects import ProjectCreate
from app.services.censopas_provisioning_service import CensopasProvisioningService
from app.services.project_service import ProjectService
from app.models.user import Organization, OrganizationMembership


async def test_short_form_rejects_population_above_24(client: AsyncClient, seed_user) -> None:
    response = await client.post(
        "/api/v1/quick-eval",
        headers={"Authorization": f"Bearer {create_access_token(seed_user.id)}"},
        json={
            "company_name": "Empresa de prueba",
            "company_ruc": "20999999999",
            "company_sector": "MINING",
            "instrument_version": "SHORT",
            "study_name": "Evaluación corta",
            "population_invited": 25,
        },
    )
    assert response.status_code == 409
    assert "versión media" in str(response.json())


async def test_company_cannot_claim_a_second_free_report(
    client: AsyncClient, session, seed_user
) -> None:
    organization = Organization(
        name="Empresa Aurora",
        tax_id="20123456789",
        status="ACTIVE",
        free_report_claimed_at=datetime.now(UTC),
        free_report_project_id=None,
    )
    session.add(organization)
    await session.flush()
    session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=seed_user.id,
            role_code="OWNER",
            permissions={},
        )
    )
    await session.commit()

    response = await client.post(
        "/api/v1/quick-eval",
        headers={"Authorization": f"Bearer {create_access_token(seed_user.id)}"},
        json={
            "company_name": "Empresa Aurora",
            "company_ruc": "20 123 456 789",
            "company_sector": "MINING",
            "instrument_version": "MEDIUM",
            "study_name": "Segunda evaluación gratuita",
            "population_invited": 250,
        },
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "CONFLICT"
    assert response.json()["free_report_claimed"] is True
    assert response.json()["project_id"] is None


async def test_claiming_free_report_is_persisted_atomically(
    session, seed_user, monkeypatch
) -> None:
    organization = Organization(name="Operación Andina", tax_id="20987654321", status="ACTIVE")
    session.add(organization)
    await session.flush()
    session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=seed_user.id,
            role_code="OWNER",
            permissions={},
        )
    )
    await session.commit()

    monkeypatch.setattr(
        CensopasProvisioningService,
        "provision_project",
        AsyncMock(return_value=None),
    )
    service = ProjectService(session)
    first = await service.create(
        ProjectCreate(
            owner_user_id=seed_user.id,
            organization_id=organization.id,
            name="Informe gratuito Aurora",
            project_type="CENSO",
        ),
        claim_free_report=True,
    )
    await session.refresh(organization)

    assert organization.free_report_claimed_at is not None
    assert organization.free_report_project_id == first.id

    with pytest.raises(ConflictError):
        await service.create(
            ProjectCreate(
                owner_user_id=seed_user.id,
                organization_id=organization.id,
                name="Segundo informe gratuito",
                project_type="CENSO",
            ),
            claim_free_report=True,
        )
