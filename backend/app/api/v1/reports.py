from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.core.exceptions import NotFoundError
from app.schemas.reports import (
    ReportPreviewRead,
    ReportRunCreate,
    ReportRunRead,
    ReportTemplateCreate,
    ReportTemplateRead,
)
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])
logger = logging.getLogger(__name__)


async def _complete_report_preview_job(
    report_id: int,
    payload: ReportRunCreate,
) -> None:
    """Ejecuta el render pesado fuera del ciclo de la petición inicial."""
    try:
        async with AsyncSessionLocal() as session:
            await ReportService(session).complete_preview(report_id, payload)
    except Exception:
        # `complete_preview` ya persiste el estado FAILED y el mensaje. El log
        # conserva el traceback para soporte sin dejar una excepción huérfana.
        logger.exception("Falló la generación asíncrona del reporte %s", report_id)


@router.post("/report-templates", response_model=ReportTemplateRead, status_code=201)
async def create_report_template(
    payload: ReportTemplateCreate, session: AsyncSession = Depends(get_db)
):
    service = ReportService(session)
    template = await service.create_template(payload)
    return ReportTemplateRead.model_validate(template)


@router.post("/studies/{study_id}/reports", response_model=ReportRunRead, status_code=201)
async def generate_report(
    study_id: int, payload: ReportRunCreate, session: AsyncSession = Depends(get_db)
):
    service = ReportService(session)
    report = await service.generate(study_id, payload)
    return ReportRunRead.model_validate(report)


@router.post("/studies/{study_id}/reports/preview", response_model=ReportPreviewRead, status_code=201)
async def generate_report_preview(
    study_id: int, payload: ReportRunCreate, session: AsyncSession = Depends(get_db)
):
    service = ReportService(session)
    report_run, pages = await service.generate_preview(study_id, payload)
    return ReportPreviewRead(
        preview_id=report_run.id,
        status=report_run.status,
        pages=pages,
        preview_url=f"/reports/{report_run.id}/preview.pdf",
    )


@router.post(
    "/studies/{study_id}/reports/preview-async",
    response_model=ReportPreviewRead,
    status_code=202,
)
async def start_report_preview(
    study_id: int,
    payload: ReportRunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    """Inicia el expediente y devuelve control sin bloquear la plataforma."""
    service = ReportService(session)
    report_run = await service.start_preview(study_id, payload)
    background_tasks.add_task(_complete_report_preview_job, report_run.id, payload)
    return ReportPreviewRead(
        preview_id=report_run.id,
        status=report_run.status,
        pages=None,
        preview_url=f"/reports/{report_run.id}/preview.pdf",
    )


@router.get("/reports/{report_id}/preview-status", response_model=ReportPreviewRead)
async def get_report_preview_status(
    report_id: int,
    session: AsyncSession = Depends(get_db),
):
    service = ReportService(session)
    report_run, pages = await service.get_preview_status(report_id)
    return ReportPreviewRead(
        preview_id=report_run.id,
        status=report_run.status,
        pages=pages,
        preview_url=f"/reports/{report_run.id}/preview.pdf",
    )


@router.get("/studies/{study_id}/reports/latest-preview", response_model=ReportPreviewRead | None)
async def get_latest_report_preview(
    study_id: int,
    session: AsyncSession = Depends(get_db),
):
    latest = await ReportService(session).get_latest_preview(study_id)
    if latest is None:
        return None
    report_run, pages = latest
    return ReportPreviewRead(
        preview_id=report_run.id,
        status=report_run.status,
        pages=pages,
        preview_url=f"/reports/{report_run.id}/preview.pdf",
    )


@router.get("/reports/{report_id}", response_model=ReportRunRead)
async def get_report(report_id: int, session: AsyncSession = Depends(get_db)):
    service = ReportService(session)
    report = await service.get_run(report_id)
    return ReportRunRead.model_validate(report)


@router.get("/reports/{report_id}/preview.pdf")
async def download_report_preview(report_id: int, session: AsyncSession = Depends(get_db)):
    service = ReportService(session)
    report = await service.get_run(report_id)
    if report.status != "COMPLETED" or not report.storage_path or not report.storage_path.endswith(".docx"):
        raise NotFoundError(f"Reporte {report_id} no tiene una vista previa disponible todavía")

    pdf_path = Path(report.storage_path).with_suffix(".pdf")
    if not pdf_path.exists():
        raise NotFoundError(f"Vista previa del reporte {report_id} no encontrada en almacenamiento")

    # `filename=` hace que FileResponse mande Content-Disposition: attachment
    # por defecto — eso fuerza una descarga y deja el <iframe> del preview en
    # blanco. La vista previa debe abrirse inline; la descarga real vive en
    # /reports/{id}/download.
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{pdf_path.name}"'},
    )


@router.get("/reports/{report_id}/download.pdf")
async def download_report_pdf(report_id: int, session: AsyncSession = Depends(get_db)):
    """Descarga el mismo PDF validado que se muestra en la vista previa."""
    service = ReportService(session)
    report = await service.get_run(report_id)
    if report.status != "COMPLETED" or not report.storage_path or not report.storage_path.endswith(".docx"):
        raise NotFoundError(f"Reporte {report_id} no tiene un PDF disponible todavía")

    pdf_path = Path(report.storage_path).with_suffix(".pdf")
    if not pdf_path.exists():
        raise NotFoundError(f"PDF del reporte {report_id} no encontrado en almacenamiento")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"Aurora_Expediente_Tecnico_{report_id}.pdf",
    )


@router.get("/reports/{report_id}/download")
async def download_report(report_id: int, session: AsyncSession = Depends(get_db)):
    service = ReportService(session)
    report = await service.get_run(report_id)
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
    return FileResponse(path=path, media_type=media_type, filename=path.name)
