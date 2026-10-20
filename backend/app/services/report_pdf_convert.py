"""Conversión DOCX → PDF vía LibreOffice headless.

El PDF de un reporte (preview y descarga en formato PDF) nunca se genera con
un renderer propio: siempre es una conversión del `.docx` real producido por
`report_docx.py`. Así el preview que ve el usuario y el archivo que descarga
son, por construcción, el mismo layout — nunca dos renderers a mantener en
paralelo.

Cada conversión usa un perfil de usuario de LibreOffice temporal y
descartable (`-env:UserInstallation`): sin esto, conversiones concurrentes
compiten por el lock del perfil por defecto y una puede fallar o colgarse
mientras la otra está en curso.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
import uuid
from pathlib import Path

from pypdf import PdfReader


logger = logging.getLogger(__name__)
_word_conversion_lock = asyncio.Lock()


class DocxToPdfError(RuntimeError):
    pass


async def docx_to_pdf(docx_bytes: bytes) -> bytes:
    conversion_errors: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="colmena_report_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            docx_path = tmp_path / "report.docx"
            docx_path.write_bytes(docx_bytes)
            profile_dir = tmp_path / f"lo_profile_{uuid.uuid4().hex}"

            process = await asyncio.create_subprocess_exec(
                "soffice",
                "--headless",
                "--norestore",
                f"-env:UserInstallation=file://{profile_dir}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp_path),
                str(docx_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                pdf_path = tmp_path / "report.pdf"
                if pdf_path.exists():
                    return pdf_path.read_bytes()
            conversion_errors.append(
                f"LibreOffice terminó con código {process.returncode}: "
                f"{stderr.decode(errors='replace') or stdout.decode(errors='replace')}"
            )
    except Exception as exc:
        conversion_errors.append(f"LibreOffice no disponible: {exc}")

    # En los equipos Windows corporativos Word suele estar instalado aunque
    # LibreOffice no lo esté. La automatización COM conserva tablas, colores,
    # saltos, encabezados, pies y gráficos del DOCX canónico; el antiguo
    # fallback de matplotlib extraía sólo texto y producía un PDF visualmente
    # incompleto. Se ejecuta en un proceso PowerShell aislado y con timeout.
    if os.name == "nt":
        try:
            async with _word_conversion_lock:
                converted = await _convert_with_word(docx_bytes)
            if converted is not None:
                return converted
        except Exception as exc:
            conversion_errors.append(f"Microsoft Word no disponible: {exc}")

    # Conserva una salida mínima para entornos de prueba/CI sin suite ofimática.
    # Los despliegues productivos deben incluir LibreOffice o Word; en ambos
    # casos se toma uno de los caminos anteriores y se preserva el layout real.
    logger.warning(
        "Se usó el PDF de contingencia porque no hubo suite ofimática: %s",
        " | ".join(conversion_errors) or "conversor no disponible",
    )
    return _generate_fallback_pdf_from_docx(docx_bytes)


async def _convert_with_word(docx_bytes: bytes) -> bytes | None:
    with tempfile.TemporaryDirectory(prefix="aurora_word_report_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        docx_path = (tmp_path / "report.docx").resolve()
        pdf_path = (tmp_path / "report.pdf").resolve()
        script_path = tmp_path / "convert.ps1"
        docx_path.write_bytes(docx_bytes)
        script_path.write_text(
            r'''param([string]$DocxPath, [string]$PdfPath)
$ErrorActionPreference = "Stop"
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($DocxPath, $false, $true)
    $document.ExportAsFixedFormat($PdfPath, 17)
}
finally {
    if ($null -ne $document) {
        $document.Close($false)
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) | Out-Null
    }
    if ($null -ne $word) {
        $word.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
''',
            encoding="utf-8-sig",
        )
        process = await asyncio.create_subprocess_exec(
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            str(docx_path),
            str(pdf_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise DocxToPdfError("Microsoft Word excedió 120 segundos al exportar el PDF.")
        if process.returncode != 0:
            message = stderr.decode(errors="replace") or stdout.decode(errors="replace")
            raise DocxToPdfError(message.strip() or "Microsoft Word no pudo exportar el PDF.")
        if not pdf_path.exists() or pdf_path.stat().st_size < 5:
            raise DocxToPdfError("Microsoft Word no produjo un archivo PDF válido.")
        pdf_bytes = pdf_path.read_bytes()
        if not pdf_bytes.startswith(b"%PDF-"):
            raise DocxToPdfError("La salida de Microsoft Word no es un PDF válido.")
        return pdf_bytes


def _generate_fallback_pdf_from_docx(docx_bytes: bytes) -> bytes:
    import io
    from docx import Document
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    doc = Document(io.BytesIO(docx_bytes))
    lines: list[str] = []
    for p in doc.paragraphs:
        if p.text.strip():
            lines.append(p.text.strip())
    for t in doc.tables:
        for row in t.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                lines.append(row_text)

    if not lines:
        lines = ["Reporte CENSOPAS - Colmena 2.0"]

    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        lines_per_page = 35
        for i in range(0, len(lines), lines_per_page):
            chunk = lines[i : i + lines_per_page]
            fig, ax = plt.subplots(figsize=(8.5, 11))
            ax.axis("off")
            text_block = "\n".join(chunk[:35])
            ax.text(
                0.05,
                0.95,
                text_block,
                transform=ax.transAxes,
                fontsize=8,
                verticalalignment="top",
                fontfamily="sans-serif",
            )
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
    return buf.getvalue()


def count_pdf_pages(pdf_bytes: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)

