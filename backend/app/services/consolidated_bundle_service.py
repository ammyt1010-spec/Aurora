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


def build_executive_cover(bundle_label: str, entries: list[tuple]) -> bytes:
    """Portada AURORA con indicadores documentales verificables.

    No mezcla baremos ni inventa un score interinstrumento. Los análisis
    pertenecen a cada informe original firmado/autorizado.
    """
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.figure import Figure
    from matplotlib.patches import FancyBboxPatch

    fig = Figure(figsize=(8.27, 11.69), dpi=110, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch(
        (0, 0.82), 1, 0.18, boxstyle="square,pad=0",
        facecolor="#0A1F44", edgecolor="none",
    ))
    # Firma visual boreal vectorial, sobria e imprimible.
    for offset, alpha, color in (
        (0.00, 0.65, "#00D4D8"),
        (0.028, 0.52, "#277DEB"),
        (0.056, 0.38, "#6366F1"),
    ):
        import numpy as np
        x = np.linspace(.45, 1.04, 90)
        y = .90 + offset + .034 * np.sin((x - .45) * 8)
        ax.plot(x, y, linewidth=13, alpha=alpha, color=color, solid_capstyle="round")
    ax.text(.085, .926, "AURORA", fontsize=27, weight="bold", color="white")
    ax.text(.087, .888, "P R O F E S S I O N A L", fontsize=9,
            color="#CBE7F2")
    ax.text(.086, .761, "INFORME EJECUTIVO", fontsize=10, weight="bold", color="#2671AD")
    ax.text(.086, .709, "Batería empresarial", fontsize=28, weight="bold", color="#0A1F44")
    ax.text(.086, .668, bundle_label[:90], fontsize=12, color="#4F6683")
    cards = (
        (.086, "INSTRUMENTOS", len(entries)),
        (.51, "INFORMES AUTORIZADOS", len(entries)),
    )
    for left, label, value in cards:
        ax.add_patch(FancyBboxPatch(
            (left, .534), .404, .093,
            boxstyle="round,pad=0.01,rounding_size=0.015",
            facecolor="#F3F8FD", edgecolor="#DCE7F2", linewidth=1,
        ))
        ax.text(left + .025, .593, label, fontsize=8, weight="bold", color="#5D7492")
        ax.text(left + .025, .548, str(value), fontsize=23, weight="bold", color="#153B67")
    ax.text(.086, .472, "CONTENIDO DOCUMENTAL", fontsize=10, weight="bold", color="#0A1F44")
    ax.plot([.086, .916], [.459, .459], color="#CFDFEE", linewidth=.8)
    # La batería admite un máximo de 12 estudios; caben todos en una página.
    for i, (study, report, digest, pdf_content) in enumerate(entries):
        y = .434 - i * .022
        ax.text(.09, y, f"{i+1:02d}", fontsize=9, weight="bold", color="#2779AC")
        ax.text(.14, y, study.name[:82], fontsize=8.6, color="#264262")
    ax.text(.087, .106, "LECTURA RESPONSABLE", fontsize=9, weight="bold", color="#0A1F44")
    ax.text(.087, .081,
            "Cada instrumento conserva su metodología, baremos, muestra y conclusiones.",
            fontsize=8.2, color="#506981")
    ax.text(.087, .061,
            "La consolidación documental no crea un índice conjunto ni una certificación.",
            fontsize=8.2, color="#506981")
    ax.text(.087, .029,
            "AURORA Professional · Integridad SHA-256 · Documentos fuente autorizados",
            fontsize=7.7, color="#718399")
    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        pdf.savefig(fig, dpi=110)
    fig.clear()
    return buffer.getvalue()



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
                ReportRun.output_format.in_(("PDF", "DOCX")),
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
        expected_ext = ".pdf" if report.output_format == "PDF" else ".docx"
        if base_dir not in path.parents or path.suffix.lower() != expected_ext or not path.is_file():
            raise ConflictError("No se encontró el documento autorizado de un estudio.")
        source_size = path.stat().st_size
        size_total += source_size
        if source_size <= 0 or source_size > MAX_SOURCE_BYTES or size_total > MAX_TOTAL_BYTES:
            raise ConflictError("Uno o más informes exceden el tamaño admitido para consolidación.")
        source = path.read_bytes()
        digest = hashlib.sha256(source).hexdigest()
        if digest != report.data_hash:
            raise ConflictError("El hash de integridad de un informe no coincide con su archivo.")
        if report.output_format == "DOCX":
            # La pantalla Informe crea DOCX oficial y su PDF visual. Reconvertimos
            # desde el DOCX cuya integridad verificamos, sin confiar en un PDF
            # auxiliar que carece de un hash propio persistido.
            from app.services.report_pdf_convert import docx_to_pdf
            content = await docx_to_pdf(source)
        else:
            content = source
        if len(content) > MAX_SOURCE_BYTES:
            raise ConflictError("El PDF resultante excede el tamaño de consolidación.")
        all_reports.append((study, report, digest, content))

    if len(all_reports) < 2:
        raise ConflictError("Una batería consolidada requiere al menos dos informes autorizados.")

    writer = PdfWriter()
    cover_pdf = build_executive_cover(bundle.label, all_reports)
    writer.append(PdfReader(io.BytesIO(cover_pdf), strict=True))
    writer.add_outline_item("Resumen ejecutivo · Batería", 0)
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
            "source_format": report.output_format,
            "compiled_pdf_hash": hashlib.sha256(content).hexdigest(),
            "pages": len(reader.pages),
            "start_page": start_page + 1,
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
            manifest={
                "reports": manifest,
                "executive_cover_pages": 1,
                "verified_documents": len(manifest),
                "note": "Cada informe conserva su metodología y su expediente de origen. "
                        "No se calcula índice global entre instrumentos.",
            },
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
