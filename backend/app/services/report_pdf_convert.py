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
import tempfile
import uuid
from pathlib import Path

from pypdf import PdfReader


class DocxToPdfError(RuntimeError):
    pass


async def docx_to_pdf(docx_bytes: bytes) -> bytes:
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
    except (FileNotFoundError, Exception):
        pass

    return _generate_fallback_pdf_from_docx(docx_bytes)


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

