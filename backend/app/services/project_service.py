from __future__ import annotations

from datetime import UTC, datetime, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationDomainError
from app.core.pagination import Page, PageParams, paginate
from app.models.analytics_plan import AnalyticsPlan
from app.models.project import Project
from app.models.study import Study
from app.models.user import Organization, OrganizationMembership, User
from app.repositories.projects import ProjectRepository
from app.schemas.projects import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.censopas_provisioning_service import CensopasProvisioningService
from app.services.organization_service import OrganizationService


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProjectRepository(session)

    async def create(self, payload: ProjectCreate, *, claim_free_report: bool = False) -> Project:
        try:
            organization_id = payload.organization_id
            organization = None
            if payload.project_type == "CENSO":
                owner = await self.session.get(User, payload.owner_user_id)
                if owner is None:
                    raise NotFoundError(f"Usuario {payload.owner_user_id} no encontrado")
                if payload.new_organization is not None:
                    if organization_id is not None:
                        raise ValidationDomainError(
                            "Selecciona una organización existente o registra una nueva, no ambas."
                        )
                    organization = await OrganizationService(self.session).create(
                        payload.new_organization, owner, commit=False
                    )
                    organization_id = organization.id
                elif organization_id is not None:
                    organization = await self.session.get(Organization, organization_id)
                    membership = (
                        await self.session.execute(
                            select(OrganizationMembership).where(
                                OrganizationMembership.organization_id == organization_id,
                                OrganizationMembership.user_id == owner.id,
                            )
                        )
                    ).scalars().first()
                    if membership is None:
                        raise AuthorizationError(
                            "Debes pertenecer a la organización para crear el proyecto."
                        )
                else:
                    raise ValidationDomainError(
                        "Un proyecto CENSOPAS requiere una organización."
                    )
            project_metadata = dict(payload.metadata or {})
            if payload.project_type == "CENSO" and payload.censopas_study is not None:
                project_metadata["requested_version_kind"] = payload.censopas_study.instrument_version
                project_metadata["analytics_plan_code"] = payload.censopas_study.analytics_plan
            project = Project(
                owner_user_id=payload.owner_user_id,
                organization_id=organization_id,
                name=payload.name,
                project_type=payload.project_type,
                description=payload.description,
                metadata_=project_metadata,
            )
            project = await self.repo.create(project)
            if project.project_type == "CENSO":
                await CensopasProvisioningService(self.session).provision_project(project)
                if payload.censopas_study is not None:
                    await self._create_initial_study(project, payload.censopas_study)
                if claim_free_report:
                    if organization is None:
                        organization = await self.session.get(Organization, organization_id)
                    if organization is None:
                        raise ValidationDomainError("No se encontró la empresa del informe gratuito.")
                    if organization.free_report_claimed_at is not None:
                        raise ConflictError(
                            "Esta empresa ya utilizó su informe gratuito de Aurora.",
                            free_report_claimed=True,
                            project_id=organization.free_report_project_id,
                        )
                    organization.free_report_claimed_at = datetime.now(UTC)
                    organization.free_report_project_id = project.id
            await self.session.commit()
            await self.session.refresh(project)
            return project
        except Exception:
            await self.session.rollback()
            raise

    async def _create_initial_study(self, project: Project, config) -> Study:
        survey_id = (project.metadata_ or {}).get("survey_id")
        if survey_id is None:
            raise ValidationDomainError("El proyecto CENSOPAS no tiene formulario provisionado.")
        plan = (
            await self.session.execute(
                select(AnalyticsPlan).where(
                    AnalyticsPlan.code == config.analytics_plan, AnalyticsPlan.is_active.is_(True)
                )
            )
        ).scalars().first()
        if plan is None:
            raise ValidationDomainError(
                f"El plan analítico '{config.analytics_plan}' no está disponible."
            )
        start_at = (
            datetime.combine(config.period_start, time.min, tzinfo=UTC)
            if config.period_start
            else None
        )
        end_at = (
            datetime.combine(config.period_end, time.max, tzinfo=UTC)
            if config.period_end
            else None
        )
        settings = {
            **(config.settings or {}),
            "workplace_name": config.workplace_name,
            "population_invited": config.population_invited,
        }
        study = Study(
            project_id=project.id,
            survey_id=int(survey_id),
            instrument_version_id=(project.metadata_ or {}).get("instrument_version_id"),
            analytics_plan_id=plan.id,
            name=project.name,
            study_type="CENSO",
            barem_id=(project.metadata_ or {}).get("barem_id"),
            start_at=start_at,
            end_at=end_at,
            settings=settings,
            requires_invitation=config.requires_invitation,
        )
        self.session.add(study)
        await self.session.flush()
        project.metadata_ = {**(project.metadata_ or {}), "censopas_study_id": study.id}
        return study

    async def get(self, project_id: int) -> Project:
        project = await self.repo.get(project_id)
        if project is None:
            raise NotFoundError(f"Proyecto {project_id} no encontrado")
        # Repara proyectos CensoPÁS creados por una instancia anterior del
        # backend antes de activar el aprovisionamiento automático.
        if project.project_type == "CENSO" and not (project.metadata_ or {}).get("censopas_auto_provisioned"):
            await CensopasProvisioningService(self.session).provision_project(project)
            await self.session.commit()
            await self.session.refresh(project)
        return project

    async def ensure_access(self, project: Project, user: User, *, write: bool) -> None:
        if project.owner_user_id == user.id:
            return
        if project.project_type != "CENSO" or project.organization_id is None:
            raise AuthorizationError("No tienes acceso a este proyecto.")
        membership = (
            await self.session.execute(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == project.organization_id,
                    OrganizationMembership.user_id == user.id,
                )
            )
        ).scalars().first()
        if membership is None or (write and membership.role_code not in {"OWNER", "ADMIN"}):
            raise AuthorizationError("No tienes permisos para esta operación.")

    async def list(self, params: PageParams, owner_user_id: int) -> Page[ProjectRead]:
        items, total = await paginate(
            self.session, self.repo.list_stmt(owner_user_id), params
        )
        return Page[ProjectRead](
            items=[ProjectRead.model_validate(item) for item in items],
            page=params.page,
            page_size=params.page_size,
            total=total,
        )

    async def update(self, project_id: int, payload: ProjectUpdate) -> Project:
        project = await self.get(project_id)
        data = payload.model_dump(exclude_unset=True)
        if "metadata" in data:
            project.metadata_ = data.pop("metadata")
        for field, value in data.items():
            setattr(project, field, value)
        await self.session.commit()
        await self.session.refresh(project)
        return project
