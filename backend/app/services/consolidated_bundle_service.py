"""Compilación de informes PDF autorizados, sin recalcular ni alterar estudios."""
from __future__ import annotations

import hashlib
import io
import uuid
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from sqlalchemy import select

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.billing import ReportOrder
from app.models.consolidated_bundle_report import ConsolidatedBundleReport
from app.models.evaluation_bundle import EvaluationBundle
from app.models.report import ReportRun
from app.models.study import Study
from app.services.audit_service import AuditService

MAX_SOURCE_BYTES = 30 * 1024 * 1024
MAX_TOTAL_BYTES = 120 * 1024 * 1024


async def combine_paid_bundle_reports(db, bundle: EvaluationBundle, user_id: int) -> ConsolidatedBundleReport:
    if bundle.status != "PUBLISHED":
        raise ConflictError("La batería está revocada. No es posible generar nuevos consolidados.")
    all_reports = []
    base_dir = (Path(get_settings().export_storage_dir).parent / "reports_storage").resolve()
    size_total = 0
    for study_id in bundle.study_ids:
        study = await db.get(Study, study_id)
        if not study or study.project_id != bundle.project_id:
            raise ConflictError("La batería contiene un estudio no válido para esta empresa.")
        report = (await db.execute(
            select(ReportRun)
            .where(
                ReportRun.study_id == study_id,
                ReportRun.status == "COMPLETED",
                ReportRun.output_format == "PDF",
                ReportRun.billing_order_id.is_not(None),
            )
            .order_by(ReportRun.created_at.desc(), ReportRun.id.desc())
            .limit(1)
        )).scalar_one_or_none()
        if not report or (report.metadata_ or {}).get("is_sample_preview"):
            raise ConflictError(f"El estudio {study.name} requiere un informe PDF definitivo con orden pagada.")
        order = await db.get(ReportOrder, report.billing_order_id)
        if order is None or order.study_id != study_id or order.status != "CONSUMED":
            raise ConflictError("Se detectó una orden comercial no válida para consolidar el informe.")
        path = Path(report.storage_path or "").resolve()
        if base_dir not in path.parents or path.suffix.lower() != ".pdf" or not path.is_file():
            raise ConflictError("No se encontró el archivo PDF autorizado de un estudio.")
        source_size = path.stat().st_size
        size_total += source_size
        if source_size <= 0 or source_size > MAX_SOURCE_BYTES or size_total > MAX_TOTAL_BYTES:
            raise ConflictError("Uno o más informes exceden el tamaño admitido para consolidación.")
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != report.data_hash:
            raise ConflictError("El hash de integridad de un informe no coincide con su archivo.")
        all_reports.append((study, report, digest, content))

    if len(all_reports) < 2:
        raise ConflictError("Una batería consolidada requiere al menos dos informes autorizados.")

    writer = PdfWriter()
    manifest = []
    for study, report, digest, content in all_reports:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted or len(reader.pages) == 0:
            raise ConflictError("Un PDF de origen está cifrado o vacío.")
        start_page = len(writer.pages)
        writer.append(reader)
        writer.add_outline_item(study.name[:100], start_page)
        manifest.append({
            "study_id": study.id,
            "study_name": study.name,
            "report_id": report.id,
            "source_hash": digest,
            "pages": len(reader.pages),
        })
    writer.add_metadata({
        "/Title": "AURORA Professional | Compilación corporativa",
        "/Subject": "Compilación de informes técnicos independientes ya autorizados",
        "/Creator": "AURORA Professional",
    })
    buffer = io.BytesIO()
    writer.write(buffer)
    pdf_bytes = buffer.getvalue()
    consolidated_dir = base_dir / "consolidated"
    consolidated_dir.mkdir(parents=True, exist_ok=True)
    destination = consolidated_dir / f"{uuid.uuid4()}.pdf"
    destination.write_bytes(pdf_bytes)

    try:
        result = ConsolidatedBundleReport(
            bundle_id=bundle.id,
            created_by_user_id=user_id,
            manifest={"reports": manifest, "note": "Cada informe conserva su metodología y su expediente de origen."},
            storage_path=str(destination),
            data_hash=hashlib.sha256(pdf_bytes).hexdigest(),
        )
        db.add(result)
        await db.flush()
        await AuditService(db).log(
            action="CONSOLIDATED_BUNDLE_REPORT_CREATED",
            entity_type="consolidated_bundle_report", entity_id=result.id,
            project_id=bundle.project_id, organization_id=bundle.organization_id, user_id=user_id,
        )
        await db.commit()
        await db.refresh(result)
        return result
    except Exception:
        destination.unlink(missing_ok=True)
        raise


async def get_consolidated_bundle_report(db, report_id: int) -> ConsolidatedBundleReport:
    report = await db.get(ConsolidatedBundleReport, report_id)
    if report is None:
        raise NotFoundError("Consolidado no encontrado.")
    return report
