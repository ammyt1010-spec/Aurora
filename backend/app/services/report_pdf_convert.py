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

from app.core.exceptions import ColmenaDomainError
import shutil


def get_soffice_binary() -> str:
    """Resolve soffice executable path across PATH and Windows default install directories."""
    in_path = shutil.which("soffice")
    if in_path:
        return in_path
    for win_candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        if Path(win_candidate).exists():
            return win_candidate
    return "soffice"


class DocxToPdfError(ColmenaDomainError):
    http_status = 503
    error_code = "REPORT_CONVERSION_UNAVAILABLE"


async def docx_to_pdf(docx_bytes: bytes) -> bytes:
    try:
        with tempfile.TemporaryDirectory(prefix="colmena_report_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            docx_path = tmp_path / "report.docx"
            docx_path.write_bytes(docx_bytes)
            profile_dir = tmp_path / f"lo_profile_{uuid.uuid4().hex}"
            soffice_bin = get_soffice_binary()

            process = await asyncio.create_subprocess_exec(
                soffice_bin,
                "--headless",
                "--norestore",
                f"-env:UserInstallation={profile_dir.as_uri()}",
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
                raise DocxToPdfError("LibreOffice terminó sin errores pero no produjo el archivo PDF esperado.")
            err_msg = stderr.decode("utf-8", errors="replace").strip() if stderr else ""
            raise DocxToPdfError(
                f"LibreOffice falló con código {process.returncode} al convertir el documento: {err_msg}"
            )
    except FileNotFoundError as exc:
        raise DocxToPdfError(
            "LibreOffice no está instalado o no se encuentra en el PATH del sistema. "
            "No es posible generar una conversión PDF fiel del documento original."
        ) from exc
    except DocxToPdfError:
        raise
    except Exception as exc:
        raise DocxToPdfError(f"Error inesperado al convertir el informe DOCX a PDF mediante LibreOffice: {exc}") from exc


def count_pdf_pages(pdf_bytes: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)

