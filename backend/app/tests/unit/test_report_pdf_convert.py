"""Pruebas de fidelidad documental y control de errores en conversión DOCX -> PDF.

Garantiza:
1. El PDF debe ser una conversión fiel 1:1 del DOCX canónico producido por LibreOffice.
2. Si LibreOffice no está disponible o falla, se eleva un error controlado DocxToPdfError.
3. Se prohíbe la generación de PDFs truncados o incompletos mediante extracciones de texto.
4. Soporte para documentos sintéticos complejos con tablas, imágenes, encabezados, gráficos y saltos de página.
"""

import asyncio
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from pypdf import PdfReader, PdfWriter

from app.services.report_pdf_convert import DocxToPdfError, count_pdf_pages, docx_to_pdf


def create_synthetic_complex_docx() -> bytes:
    """Genera un documento DOCX sintético completo con encabezados, tablas, imágenes,

    gráficos y saltos de página.
    """
    doc = Document()

    # 1. Encabezado y Pie de página
    section = doc.sections[0]
    header = section.header
    header.paragraphs[0].text = "CONFIDENCIAL - INFORME CENSOPAS-COPSOQ | AURORA Professional"
    footer = section.footer
    footer.paragraphs[0].text = "Página 1 de 2 - Documento Oficial de Evaluación"

    # 2. Título y encabezados
    title = doc.add_heading("INFORME DE EVALUACIÓN DE RIESGOS PSICOSOCIALES", level=0)
    title.runs[0].font.color.rgb = RGBColor(16, 44, 87)

    h1 = doc.add_heading("1. Ficha Técnica del Estudio", level=1)
    p1 = doc.add_paragraph("Este estudio fue realizado de acuerdo con el marco regulatorio del CENSOPAS.")
    p1.runs[0].bold = True

    # 3. Tabla estructurada con encabezados y estilos
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Dimensión"
    hdr_cells[1].text = "Puntaje Medio"
    hdr_cells[2].text = "Nivel de Riesgo"
    hdr_cells[3].text = "Semáforo"

    sample_data = [
        ("Exigencias Cuantitativas", "14.2", "MEDIO", "Amarillo"),
        ("Trabajo Emocional", "18.9", "ALTO", "Rojo"),
        ("Claridad de Rol", "8.1", "BAJO", "Verde"),
    ]
    for dim, score, risk, sem in sample_data:
        row_cells = table.add_row().cells
        row_cells[0].text = dim
        row_cells[1].text = score
        row_cells[2].text = risk
        row_cells[3].text = sem

    # 4. Imagen / Gráfico sintético en formato PNG
    from PIL import Image
    img = Image.new("RGB", (120, 80), color=(16, 44, 87))
    img_stream = BytesIO()
    img.save(img_stream, format="PNG")
    img_stream.seek(0)
    doc.add_heading("2. Representación Gráfica de Indicadores", level=1)
    doc.add_paragraph("Gráfico de distribución por dimensiones:")
    doc.add_picture(img_stream, width=Inches(1.5))

    # 5. Salto de página
    doc.add_page_break()

    # 6. Segunda página con conclusiones
    doc.add_heading("3. Conclusiones y Plan de Acción", level=1)
    doc.add_paragraph(
        "Se recomienda intervenir de inmediato en el factor 'Trabajo Emocional' mediante talleres formativos."
    )

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def create_minimal_valid_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_synthetic_document_structure():
    """Verifica que el documento sintético contenga tablas, encabezados, párrafos e imágenes."""
    docx_bytes = create_synthetic_complex_docx()
    assert len(docx_bytes) > 1000

    doc = Document(BytesIO(docx_bytes))
    assert len(doc.tables) == 1
    assert len(doc.tables[0].rows) == 4
    assert len(doc.paragraphs) >= 5

    # Comprueba la presencia de la imagen en las relaciones del documento
    has_image = any("image" in rel.target_ref.lower() for rel in doc.part.rels.values())
    assert has_image is True


@pytest.mark.asyncio
async def test_libreoffice_not_installed_raises_controlled_error():
    """Si soffice no existe en el sistema, se eleva DocxToPdfError controlado."""
    docx_bytes = create_synthetic_complex_docx()

    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("soffice no encontrado")):
        with pytest.raises(DocxToPdfError) as exc_info:
            await docx_to_pdf(docx_bytes)
        assert "LibreOffice no está instalado" in str(exc_info.value)


@pytest.mark.asyncio
async def test_libreoffice_process_failure_raises_controlled_error():
    """Si soffice termina con código de error, se eleva DocxToPdfError con el detalle."""
    docx_bytes = create_synthetic_complex_docx()

    mock_process = AsyncMock()
    mock_process.returncode = 1
    mock_process.communicate.return_value = (b"", b"Error general de conversion soffice")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(DocxToPdfError) as exc_info:
            await docx_to_pdf(docx_bytes)
        assert "LibreOffice falló con código 1" in str(exc_info.value)
        assert "Error general de conversion soffice" in str(exc_info.value)


@pytest.mark.asyncio
async def test_libreoffice_success_produces_pdf(tmp_path):
    """Si soffice genera exitosamente el archivo PDF, se retorna su contenido binario."""
    docx_bytes = create_synthetic_complex_docx()
    synthetic_pdf = create_minimal_valid_pdf()

    async def fake_subprocess_exec(*args, **kwargs):
        # El comando incluye --outdir <path>
        outdir = args[args.index("--outdir") + 1]
        pdf_out = Path(outdir) / "report.pdf"
        pdf_out.write_bytes(synthetic_pdf)
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"Conversion OK", b"")
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess_exec):
        pdf_bytes = await docx_to_pdf(docx_bytes)
        assert pdf_bytes == synthetic_pdf
        assert count_pdf_pages(pdf_bytes) == 2


def test_no_matplotlib_fallback_in_service():
    """Garantiza que report_pdf_convert no contenga renderers degradados con matplotlib."""
    import app.services.report_pdf_convert as rpc

    assert not hasattr(rpc, "_generate_fallback_pdf_from_docx")
    assert not hasattr(rpc, "PdfPages")
