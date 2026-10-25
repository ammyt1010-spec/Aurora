"""Crea dos usuarios demo, cada uno con un proyecto CensoPÁS diferente.

El seed es idempotente: identifica sus registros mediante ``seed_key`` y,
cuando se vuelve a ejecutar, actualiza los datos demo sin duplicarlos. Antes
de crear los proyectos garantiza que estén instaladas las versiones oficiales
SHORT y MEDIUM del instrumento CENSOPAS-COPSOQ.

Uso (desde ``backend/``):

    .venv/bin/python scripts/seed_two_censopas_users.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.models.project import Project
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.projects import ProjectCreate
from app.services.censopas_provisioning_service import CensopasProvisioningService
from app.services.project_service import ProjectService
from scripts.seed_censopas_official import run as seed_official_catalog

SEED_VERSION = "TWO_CENSOPAS_USERS_V1"


@dataclass(frozen=True)
class DemoSpec:
    email: str
    username: str
    first_name: str
    last_name: str
    organization_name: str
    organization_tax_id: str
    project_name: str
    project_description: str
    version_kind: str

    @property
    def seed_key(self) -> str:
        return f"{SEED_VERSION}:{self.username}"


DEMO_SPECS = (
    DemoSpec(
        email="ana.torres@censopas.demo",
        username="ana.censopas",
        first_name="Ana",
        last_name="Torres",
        organization_name="Industrias Andinas Demo",
        organization_tax_id="20100000001",
        project_name="Diagnóstico CensoPÁS — Industrias Andinas",
        project_description=(
            "Evaluación demo con el plan corto CENSOPAS-COPSOQ para personal "
            "operativo de Industrias Andinas."
        ),
        version_kind="SHORT",
    ),
    DemoSpec(
        email="carlos.mendoza@censopas.demo",
        username="carlos.censopas",
        first_name="Carlos",
        last_name="Mendoza",
        organization_name="Servicios del Pacífico Demo",
        organization_tax_id="20100000002",
        project_name="Evaluación CensoPÁS — Servicios del Pacífico",
        project_description=(
            "Evaluación demo con el plan medio CENSOPAS-COPSOQ para las sedes "
            "de Servicios del Pacífico."
        ),
        version_kind="MEDIUM",
    ),
)


async def _upsert_user(session: AsyncSession, spec: DemoSpec, password: str) -> User:
    user = (
        await session.execute(select(User).where(User.email == spec.email))
    ).scalars().first()
    if user is None:
        user = User(email=spec.email, username=spec.username)
        session.add(user)

    user.username = spec.username
    user.password_hash = hash_password(password)
    user.first_name = spec.first_name
    user.last_name = spec.last_name
    user.status = "ACTIVE"
    user.metadata_ = {
        **(user.metadata_ or {}),
        "demo": True,
        "seed_key": spec.seed_key,
        "seed_version": SEED_VERSION,
    }
    await session.flush()
    return user


async def _upsert_organization(
    session: AsyncSession, user: User, spec: DemoSpec
) -> Organization:
    memberships = list(
        (
            await session.execute(
                select(OrganizationMembership).where(
                    OrganizationMembership.user_id == user.id
                )
            )
        ).scalars()
    )
    organization = None
    for membership in memberships:
        candidate = await session.get(Organization, membership.organization_id)
        if candidate is not None and (candidate.metadata_ or {}).get("seed_key") == spec.seed_key:
            organization = candidate
            break

    if organization is None:
        organization = Organization(
            name=spec.organization_name,
            legal_name=spec.organization_name,
            tax_id=spec.organization_tax_id,
            organization_type="PRIVATE_COMPANY",
            status="ACTIVE",
            metadata_={
                "demo": True,
                "seed_key": spec.seed_key,
                "seed_version": SEED_VERSION,
            },
        )
        session.add(organization)
        await session.flush()
        session.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role_code="OWNER",
                permissions={},
            )
        )

    organization.name = spec.organization_name
    organization.legal_name = spec.organization_name
    organization.tax_id = spec.organization_tax_id
    organization.organization_type = "PRIVATE_COMPANY"
    organization.status = "ACTIVE"
    organization.metadata_ = {
        **(organization.metadata_ or {}),
        "demo": True,
        "seed_key": spec.seed_key,
        "seed_version": SEED_VERSION,
    }
    await session.flush()
    return organization


async def _upsert_project(
    session: AsyncSession,
    user: User,
    organization: Organization,
    spec: DemoSpec,
) -> Project:
    candidates = list(
        (
            await session.execute(
                select(Project).where(Project.owner_user_id == user.id)
            )
        ).scalars()
    )
    project = next(
        (
            item
            for item in candidates
            if (item.metadata_ or {}).get("seed_key") == spec.seed_key
        ),
        None,
    )
    seed_metadata = {
        "demo": True,
        "seed_key": spec.seed_key,
        "seed_version": SEED_VERSION,
        "requested_version_kind": spec.version_kind,
    }

    if project is None:
        return await ProjectService(session).create(
            ProjectCreate(
                owner_user_id=user.id,
                organization_id=organization.id,
                name=spec.project_name,
                project_type="CENSO",
                description=spec.project_description,
                metadata=seed_metadata,
            )
        )

    project.organization_id = organization.id
    project.name = spec.project_name
    project.project_type = "CENSO"
    project.description = spec.project_description
    project.status = "DRAFT"
    project.metadata_ = {**(project.metadata_ or {}), **seed_metadata}
    if not project.metadata_.get("censopas_auto_provisioned"):
        await CensopasProvisioningService(session).provision_project(project)
    await session.commit()
    await session.refresh(project)
    return project


async def run() -> list[dict]:
    password = os.environ.get("AURORA_SEED_PASSWORD", "")
    if len(password) < 16:
        raise RuntimeError("Set AURORA_SEED_PASSWORD to a unique secret of at least 16 characters")
    await seed_official_catalog()
    results: list[dict] = []
    async with AsyncSessionLocal() as session:
        for spec in DEMO_SPECS:
            try:
                user = await _upsert_user(session, spec, password)
                organization = await _upsert_organization(session, user, spec)
                await session.commit()
                project = await _upsert_project(session, user, organization, spec)
            except Exception:
                await session.rollback()
                raise

            results.append(
                {
                    "email": user.email,

                    "user_id": user.id,
                    "organization_id": organization.id,
                    "project_id": project.id,
                    "project_name": project.name,
                    "censopas_version_kind": project.metadata_.get(
                        "censopas_version_kind"
                    ),
                    "survey_id": project.metadata_.get("survey_id"),
                    "barem_id": project.metadata_.get("barem_id"),
                }
            )
    return results


async def main() -> None:
    try:
        results = await run()
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
