from __future__ import annotations

from datetime import UTC, datetime, time

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationDomainError
from app.core.pagination import Page, PageParams, paginate
from app.models.analytics_plan import AnalyticsPlan
from app.models.project import Project
from app.models.study import Study
from app.models.user import OrganizationMembership, User
from app.models.project import ProjectMember
from app.repositories.projects import ProjectRepository
from app.schemas.projects import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.censopas_provisioning_service import CensopasProvisioningService
from app.services.organization_service import OrganizationService


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProjectRepository(session)

    async def create(self, payload: ProjectCreate) -> Project:
        try:
            organization_id = payload.organization_id
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
                    # OrganizationService adds its OWNER membership after flushing
                    # the organization; autoflush=False requires an explicit flush.
                    await self.session.flush()
                elif organization_id is not None:
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
            # Production is exclusively enterprise-based. A registered
            # company with an OWNER/ADMIN must back every new project.
            from app.core.config import get_settings
            if get_settings().environment.lower() == "production":
                if organization_id is None:
                    raise ValidationDomainError("Registra o selecciona una empresa antes de crear un proyecto.")
                membership = await self.session.get(
                    OrganizationMembership, (organization_id, payload.owner_user_id)
                )
                if membership is None or membership.role_code not in {"OWNER", "ADMIN"}:
                    raise AuthorizationError("Sólo el administrador empresarial puede crear proyectos.")
            elif organization_id is not None:
                membership = await self.session.get(
                    OrganizationMembership, (organization_id, payload.owner_user_id)
                )
                if membership is None:
                    raise AuthorizationError("No puedes asociar proyectos a otra empresa.")
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

    async def get(self, project_id: int, user: User | None = None) -> Project:
        project = await self.repo.get(project_id)
        if project is None:
            raise NotFoundError(f"Proyecto {project_id} no encontrado")
        if user is not None:
            await self.ensure_access(project, user, write=False)
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
        member = await self.session.get(ProjectMember, (project.id, user.id))
        if member is not None and (not write or member.role_code in {"ADMIN", "EDITOR"}):
            return
        if project.project_type == "CENSO" and project.organization_id is not None:
            membership = await self.session.get(
                OrganizationMembership, (project.organization_id, user.id)
            )
            if membership is not None and (not write or membership.role_code in {"OWNER", "ADMIN"}):
                return
        raise AuthorizationError("No tienes permisos sobre este proyecto.")

    async def ensure_membership_admin(self, project: Project, user: User) -> None:
        if project.owner_user_id == user.id:
            return
        member = await self.session.get(ProjectMember, (project.id, user.id))
        if member is not None and member.role_code == "ADMIN":
            return
        if project.project_type == "CENSO" and project.organization_id is not None:
            org_member = await self.session.get(
                OrganizationMembership, (project.organization_id, user.id)
            )
            if org_member is not None and org_member.role_code in {"OWNER", "ADMIN"}:
                return
        raise AuthorizationError("Sólo los administradores pueden cambiar miembros.")

    async def list(self, params: PageParams, owner_user_id: int) -> Page[ProjectRead]:
        # Include projects shared directly with the user, and org projects.
        stmt = (
            select(Project)
            .where(or_(
                Project.owner_user_id == owner_user_id,
                exists(select(ProjectMember.project_id).where(
                    ProjectMember.project_id == Project.id,
                    ProjectMember.user_id == owner_user_id,
                )),
                and_(
                    Project.project_type == "CENSO",
                    exists(select(OrganizationMembership.organization_id).where(
                        OrganizationMembership.organization_id == Project.organization_id,
                        OrganizationMembership.user_id == owner_user_id,
                    )),
                ),
            ))
            .order_by(Project.created_at.desc(), Project.id.desc())
        )
        items, total = await paginate(self.session, stmt, params)
        return Page[ProjectRead](
            items=[ProjectRead.model_validate(item) for item in items],
            page=params.page,
            page_size=params.page_size,
            total=total,
        )

    async def list_members(self, project: Project, user: User) -> list[dict]:
        await self.ensure_access(project, user, write=False)
        stmt = (
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project.id)
            .order_by(User.username, User.id)
        )
        members = [
            {"user_id": member.user_id, "username": linked.username or "",
             "role_code": member.role_code}
            for member, linked in (await self.session.execute(stmt)).all()
        ]
        owner = await self.session.get(User, project.owner_user_id)
        if owner is not None:
            members.insert(0, {"user_id": owner.id, "username": owner.username or "", "role_code": "OWNER"})
        return members

    async def add_member(self, project: Project, user: User, target_user_id: int, role_code: str) -> dict:
        await self.ensure_membership_admin(project, user)
        if target_user_id == project.owner_user_id:
            raise ValidationDomainError("El propietario no requiere membresía adicional.")
        target = await self.session.get(User, target_user_id)
        if target is None or target.status != "ACTIVE":
            raise NotFoundError("El usuario seleccionado no está disponible.")
        member = await self.session.get(ProjectMember, (project.id, target_user_id))
        if member is None:
            member = ProjectMember(project_id=project.id, user_id=target_user_id,
                                   role_code=role_code, permissions={})
            self.session.add(member)
        else:
            member.role_code = role_code
        await self.session.commit()
        return {"user_id": member.user_id, "username": target.username or "", "role_code": member.role_code}

    async def remove_member(self, project: Project, user: User, target_user_id: int) -> None:
        await self.ensure_membership_admin(project, user)
        if target_user_id == project.owner_user_id:
            raise ValidationDomainError("No puedes eliminar al propietario del proyecto.")
        member = await self.session.get(ProjectMember, (project.id, target_user_id))
        if member is None:
            raise NotFoundError("Miembro no encontrado.")
        await self.session.delete(member)
        await self.session.commit()

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
