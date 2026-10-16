from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.core.synthetic_test_bypass import is_authorized_synthetic_test
from app.core.security import get_current_user, get_optional_current_user
from app.models.project import Project
from app.models.report import ReportRun
from app.models.study import Study
from app.models.user import OrganizationMembership, User
from app.schemas.reports import (
    ReportPreviewRead,
    ReportRunCreate,
    ReportRunRead,
    ReportTemplateCreate,
    ReportTemplateRead,
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


@router.post("/report-templates", response_model=ReportTemplateRead, status_code=201)
async def create_report_template(
    payload: ReportTemplateCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_operator(user)
    service = ReportService(session)
    template = await service.create_template(payload)
    return ReportTemplateRead.model_validate(template)


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
    if current_user is None:
        if not is_authorized_synthetic_test(request):
            raise AuthorizationError("Debes iniciar sesión como administrador de la empresa.")
    else:
        await BillingService(session)._organization_admin(study_id, current_user)

    service = ReportService(session)
    safe = payload.model_copy(update={"requested_by_user_id": current_user.id}) if current_user else payload
    report_run, pages = await service.generate_preview(study_id, safe, request=request)
    return ReportPreviewRead(
        preview_id=report_run.id,
        status=report_run.status,
        pages=pages,
        preview_url=f"/reports/{report_run.id}/preview.pdf",
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
