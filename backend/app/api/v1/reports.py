from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.core.synthetic_test_bypass import is_authorized_synthetic_test
from app.core.security import get_current_user, get_optional_current_user
from app.models.audit import AuditLog
from app.models.billing import ReportOrder
from app.models.project import Project
from app.models.report import ReportRun, ReportTemplate
from app.models.study import Study
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.reports import (
    ExecutiveDashboardResponse,
    ReportAuditDetailRead,
    ReportHistoryItemRead,
    ReportPreviewRead,
    ReportRunCreate,
    ReportRunRead,
    ReportTemplateCreate,
    ReportTemplateRead,
    ReportTemplateUpdate,
)
from app.services.billing_service import BillingService, is_platform_operator, require_operator
from app.services.download_audit import record_file_access
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])


async def _assert_study_access(
    session: AsyncSession, study_id: int, user: User | None, request: Request | None = None
) -> tuple[Study, Project]:
    study = await session.get(Study, study_id)
    if study is None:
        raise NotFoundError("Estudio no encontrado.")
    project = await session.get(Project, study.project_id)
    if project is None:
        raise NotFoundError("Proyecto no encontrado.")

    if user is not None:
        if not is_platform_operator(user) and not (hasattr(user, "is_superuser") and user.is_superuser):
            member = await session.get(OrganizationMembership, (project.organization_id, user.id))
            if member is None:
                raise AuthorizationError("No tienes acceso a los informes de esta empresa.")
    elif not is_authorized_synthetic_test(request):
        raise AuthorizationError("Debes iniciar sesión para consultar este informe.")

    return study, project


@router.get("/report-templates", response_model=list[ReportTemplateRead])
async def list_report_templates(
    discipline: str | None = None,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = ReportService(session)
    templates = await service.list_templates(discipline=discipline)
    return [
        ReportTemplateRead(
            id=t.id,
            public_id=t.public_id,
            code=t.code,
            name=t.name,
            report_type=t.report_type,
            discipline=(t.template_config or {}).get("discipline") or t.report_type or "PSICOSOCIAL",
            instrument_version_id=t.instrument_version_id,
            template_config=t.template_config or {},
            is_system=t.is_system,
            status=t.status,
        )
        for t in templates
    ]


@router.get("/report-templates/{template_id}", response_model=ReportTemplateRead)
async def get_report_template(
    template_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = ReportService(session)
    t = await service.repo.get_template(template_id)
    if t is None:
        raise NotFoundError(f"Plantilla {template_id} no encontrada.")
    return ReportTemplateRead(
        id=t.id,
        public_id=t.public_id,
        code=t.code,
        name=t.name,
        report_type=t.report_type,
        discipline=(t.template_config or {}).get("discipline") or t.report_type or "PSICOSOCIAL",
        instrument_version_id=t.instrument_version_id,
        template_config=t.template_config or {},
        is_system=t.is_system,
        status=t.status,
    )


@router.post("/report-templates", response_model=ReportTemplateRead, status_code=201)
async def create_report_template(
    payload: ReportTemplateCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_operator(user)
    service = ReportService(session)
    template = await service.create_template(payload)
    return ReportTemplateRead(
        id=template.id,
        public_id=template.public_id,
        code=template.code,
        name=template.name,
        report_type=template.report_type,
        discipline=(template.template_config or {}).get("discipline") or template.report_type or "PSICOSOCIAL",
        instrument_version_id=template.instrument_version_id,
        template_config=template.template_config or {},
        is_system=template.is_system,
        status=template.status,
    )


@router.put("/report-templates/{template_id}", response_model=ReportTemplateRead)
async def update_report_template(
    template_id: int,
    payload: ReportTemplateUpdate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_operator(user)
    service = ReportService(session)
    t = await service.update_template(template_id, payload)
    return ReportTemplateRead(
        id=t.id,
        public_id=t.public_id,
        code=t.code,
        name=t.name,
        report_type=t.report_type,
        discipline=(t.template_config or {}).get("discipline") or t.report_type or "PSICOSOCIAL",
        instrument_version_id=t.instrument_version_id,
        template_config=t.template_config or {},
        is_system=t.is_system,
        status=t.status,
    )


@router.post("/studies/{study_id}/reports", response_model=ReportRunRead, status_code=201)
async def generate_report(
    study_id: int,
    payload: ReportRunCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    if current_user is None:
        if not is_authorized_synthetic_test(request):
            raise AuthorizationError("Debes iniciar sesión como administrador de la empresa.")
    else:
        await BillingService(session)._organization_admin(study_id, current_user)

    service = ReportService(session)
    safe = payload.model_copy(update={"requested_by_user_id": current_user.id}) if current_user else payload
    report = await service.generate(study_id, safe, request=request)
    return ReportRunRead.model_validate(report)


@router.post("/studies/{study_id}/reports/preview", response_model=ReportPreviewRead, status_code=201)
async def generate_report_preview(
    study_id: int,
    payload: ReportRunCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    is_sample = bool(payload.is_sample_preview or payload.report_mode == "SAMPLE")
    if current_user is None and not is_sample:
        if not is_authorized_synthetic_test(request):
            raise AuthorizationError("Debes iniciar sesión como administrador de la empresa.")
    elif current_user is not None and not is_sample:
        await BillingService(session)._organization_admin(study_id, current_user)

    service = ReportService(session)
    safe = payload.model_copy(update={"requested_by_user_id": current_user.id}) if current_user else payload
    report_run, pages = await service.generate_preview(study_id, safe, request=request)
    meta = report_run.metadata_ or {}
    return ReportPreviewRead(
        preview_id=report_run.id,
        status=report_run.status,
        pages=pages,
        preview_url=f"/reports/{report_run.id}/preview.pdf",
        is_sample=bool(meta.get("is_sample_preview")),
        watermark=meta.get("watermark"),
    )


@router.get("/reports/{report_id}", response_model=ReportRunRead)
async def get_report(
    report_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = ReportService(session)
    report = await service.get_run(report_id)
    await _assert_study_access(session, report.study_id, current_user, request)
    return ReportRunRead.model_validate(report)


@router.get("/reports/{report_id}/preview.pdf")
async def download_report_preview(
    report_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = ReportService(session)
    report = await service.get_run(report_id)
    await _assert_study_access(session, report.study_id, current_user, request)
    if get_settings().environment.lower() == "production" and report.billing_order_id is None:
        raise ConflictError("Informe anterior sin autorización de entrega. Contacta al administrador.")
    if report.status != "COMPLETED" or not report.storage_path or not report.storage_path.endswith(".docx"):
        raise NotFoundError(f"Reporte {report_id} no tiene una vista previa disponible todavía")

    pdf_path = Path(report.storage_path).with_suffix(".pdf")
    if not pdf_path.exists():
        raise NotFoundError(f"Vista previa del reporte {report_id} no encontrada en almacenamiento")

    await record_file_access(
        session,
        action="REPORT_PREVIEW_OPENED",
        entity_type="report",
        entity_id=report_id,
        study_id=report.study_id,
        user_id=current_user.id if current_user else None,
    )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{pdf_path.name}"'},
    )


@router.get("/reports/{report_id}/download")
async def download_report(
    report_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = ReportService(session)
    report = await service.get_run(report_id)
    await _assert_study_access(session, report.study_id, current_user, request)
    if report.status != "COMPLETED" or not report.storage_path:
        raise NotFoundError(f"Reporte {report_id} no tiene un archivo disponible todavía")

    if (report.metadata_ or {}).get("is_sample_preview"):
        raise ConflictError("No es posible descargar el informe definitivo oficial a partir de una vista previa de muestra sin pagar.")

    path = Path(report.storage_path)
    if not path.exists():
        raise NotFoundError(f"Archivo de reporte {report_id} no encontrado en almacenamiento")

    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if path.suffix == ".docx"
        else "application/pdf"
        if path.suffix == ".pdf"
        else "application/json"
    )
    await record_file_access(
        session,
        action="REPORT_DOWNLOADED",
        entity_type="report",
        entity_id=report_id,
        study_id=report.study_id,
        user_id=current_user.id if current_user else None,
    )
    return FileResponse(path=path, media_type=media_type, filename=path.name)


@router.get("/studies/{study_id}/reports", response_model=list[ReportRunRead])
async def list_study_reports(
    study_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    """Permit re-download of an already paid report without a second charge."""
    await _assert_study_access(session, study_id, current_user, request)
    stmt = select(ReportRun).where(ReportRun.study_id == study_id).order_by(ReportRun.created_at.desc(), ReportRun.id.desc())
    return [ReportRunRead.model_validate(item) for item in (await session.execute(stmt)).scalars().all()]


@router.get("/studies/{study_id}/reports/executive-dashboard", response_model=ExecutiveDashboardResponse)
async def get_study_executive_dashboard(
    study_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    await _assert_study_access(session, study_id, current_user, request)
    service = ReportService(session)
    data = await service.get_executive_dashboard(study_id)
    return ExecutiveDashboardResponse(**data)


@router.get("/organizations/{organization_id}/reports/history", response_model=list[ReportHistoryItemRead])
async def list_organization_reports_history(
    organization_id: int,
    study_id: int | None = None,
    discipline: str | None = None,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    if current_user is not None and not is_platform_operator(current_user) and not getattr(current_user, "is_superuser", False):
        member = await session.get(OrganizationMembership, (organization_id, current_user.id))
        if member is None:
            raise AuthorizationError("No tienes acceso a los informes de esta organización.")
    service = ReportService(session)
    items = await service.get_organization_report_history(
        organization_id, study_id=study_id, discipline=discipline
    )
    return [ReportHistoryItemRead(**item) for item in items]


@router.get("/reports/{report_id}/audit", response_model=ReportAuditDetailRead)
async def get_report_audit(
    report_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    service = ReportService(session)
    report = await service.get_run(report_id)
    study, project = await _assert_study_access(session, report.study_id, current_user, request)
    org = await session.get(Organization, project.organization_id) if project and project.organization_id else None

    user_label = None
    if report.requested_by_user_id:
        user = await session.get(User, report.requested_by_user_id)
        if user:
            user_label = f"{user.email} ({user.first_name or ''} {user.last_name or ''})".strip()

    meta = report.metadata_ or {}
    template_name = meta.get("template_name")
    discipline = meta.get("discipline", "PSICOSOCIAL")
    order = await session.get(ReportOrder, report.billing_order_id) if report.billing_order_id else None

    dl_stmt = select(func.count(AuditLog.id)).where(AuditLog.entity_type == "report", AuditLog.entity_id == report.id)
    access_count = (await session.execute(dl_stmt)).scalar() or 0

    return ReportAuditDetailRead(
        report_id=report.id,
        public_id=report.public_id,
        data_hash=report.data_hash or "PENDING",
        study_id=report.study_id,
        study_name=study.name,
        organization_name=org.name if org else None,
        discipline=discipline,
        template_name=template_name,
        template_version="1.0",
        emitted_by_user=user_label,
        generated_at=report.generated_at,
        billing_order_id=report.billing_order_id,
        billing_order_status=order.status if order else None,
        integrity_verified=bool(report.data_hash),
        access_logs_count=access_count,
    )

