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
    except FileNotFoundError as exc:
        raise DocxToPdfError("LibreOffice no está instalado. No es posible generar un PDF fiel al documento.") from exc
    except Exception as exc:
        raise DocxToPdfError("Error convirtiendo el informe mediante LibreOffice.") from exc
    raise DocxToPdfError("LibreOffice no produjo el PDF solicitado. Comprueba la instalación y los permisos.")


def count_pdf_pages(pdf_bytes: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)

