"""Smoke test del design system DOCX: el bundle mínimo debe renderizar un
.docx válido y cada tabla debe llevar un único `w:tblW`/`w:tblLayout` — la
regresión concreta que rompió el ancho de las tablas del header (LibreOffice
fusiona dos `w:tbl` consecutivas sin párrafo entre medio, y un `tblPr` con
`w:tblW` duplicado hace que el renderer ignore el ancho fijado)."""

import io

from docx import Document
from docx.oxml.ns import qn

from app.services.report_docx import render_report_docx

_BUNDLE = {
    "study": {"name": "Estudio de prueba", "status": "OPEN", "study_type": "CENSO"},
    "cover": {"version_kind": "SHORT", "methodological_label": {"label": "Baremo de referencia"}},
    "sections": [],
    "traceability": {"privacy": {"min_publishable_n": 5}},
    "dimension_results": [
        {
            "construct_code": "D1",
            "construct_name": "Exigencias psicológicas",
            "favorable_pct": 20.0,
            "favorable_n": 4,
            "intermediate_pct": 30.0,
            "intermediate_n": 6,
            "unfavorable_pct": 50.0,
            "unfavorable_n": 10,
            "n_valid": 20,
            "collective_classification": "RIESGO_ALTO",
        }
    ],
}


def test_render_report_docx_produces_valid_document():
    docx_bytes = render_report_docx(_BUNDLE)
    document = Document(io.BytesIO(docx_bytes))
    assert len(document.paragraphs) > 0


def test_every_table_has_a_single_tblw_and_tbllayout():
    docx_bytes = render_report_docx(_BUNDLE)
    document = Document(io.BytesIO(docx_bytes))

    def check_tables(tables):
        for table in tables:
            tblPr = table._tbl.tblPr
            assert len(tblPr.findall(qn("w:tblW"))) <= 1, "tblW duplicado rompe el ancho en LibreOffice"
            assert len(tblPr.findall(qn("w:tblLayout"))) <= 1

    check_tables(document.tables)
    section = document.sections[0]
    check_tables(section.header.tables)
    check_tables(section.footer.tables)


if __name__ == "__main__":
    test_render_report_docx_produces_valid_document()
    test_every_table_has_a_single_tblw_and_tbllayout()
    print("ok")


def test_multidisciplinary_docx_uses_template_and_suppresses_private_scores():
    import copy

    bundle = copy.deepcopy(_BUNDLE)
    bundle.update({
        "is_censopas": False,
        "discipline": "ERGONOMIA",
        "report_template": {
            "discipline": "ERGONOMIA",
            "header_title": "Informe de evaluación ergonómica de puestos",
        },
        "cover": {
            "badge_text": "INFORME TÉCNICO AURORA",
            "instrument_label": "Instrumento Ergonómico",
            "version_kind": "V1",
        },
        "sections": ["portada", "ficha_tecnica", "dimensiones"],
        "barem_results": {
            "results": [
                {
                    "construct_name": "Postura cervical",
                    "n_valid": 2,
                    "suppressed": True,
                    "mean_score": None,
                    "bands": [],
                },
                {
                    "construct_name": "Carga postural",
                    "n_valid": 8,
                    "suppressed": False,
                    "mean_score": 61.5,
                    "bands": [{"label": "Riesgo alto", "classification_code": "RIESGO_ALTO", "pct": 75.0}],
                },
            ]
        },
    })
    doc = Document(io.BytesIO(render_report_docx(bundle)))
    body = "\n".join(
        [paragraph.text for paragraph in doc.paragraphs]
        + [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
    )
    header = "\n".join(cell.text for table in doc.sections[0].header.tables for row in table.rows for cell in row.cells)
    footer = "\n".join(cell.text for table in doc.sections[0].footer.tables for row in table.rows for cell in row.cells)

    assert "Informe de evaluación ergonómica de puestos" in header
    assert "ERGONOMIA" in footer
    assert "Resultados por constructo" in body
    assert "Postura cervical" in body
    assert "Suprimido" in body
    assert "No publicable" in body
    assert "Carga postural" in body
    assert "61.50" in body
    assert "CENSOPAS-COPSOQ" not in body + header + footer
    assert "Resultados por dimensión (D1-D6)" not in body


def _small_valid_png() -> bytes:
    import struct
    import zlib

    def chunk(name: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + name
            + payload
            + struct.pack(">I", zlib.crc32(name + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    rgb_scanline = bytes.fromhex("00ff0000")
    return (
        bytes.fromhex("89504e470d0a1a0a")
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(rgb_scanline))
        + chunk(b"IEND", b"")
    )


def test_company_logo_is_validated_and_embedded_in_docx():
    import base64
    import copy
    from app.services.report_service import ReportService

    logo = _small_valid_png()
    encoded = "data:image/png;base64," + base64.b64encode(logo).decode("ascii")
    validated = ReportService._decode_company_logo(encoded)
    assert validated == logo

    bundle = copy.deepcopy(_BUNDLE)
    base_document = Document(io.BytesIO(render_report_docx(bundle)))
    bundle["brand_logo_png"] = validated
    document = Document(io.BytesIO(render_report_docx(bundle)))
    assert len(document.inline_shapes) == len(base_document.inline_shapes) + 1


def test_company_logo_rejects_unsupported_and_oversize_inputs():
    import base64
    import pytest
    from app.core.exceptions import ValidationDomainError
    from app.services.report_service import ReportService

    with pytest.raises(ValidationDomainError):
        ReportService._decode_company_logo("data:image/svg+xml;base64,PHN2Zy8+")
    with pytest.raises(ValidationDomainError):
        ReportService._decode_company_logo("data:image/png;base64,%%%")
    oversized = _small_valid_png() + b"0" * (600 * 1024)
    payload = "data:image/png;base64," + base64.b64encode(oversized).decode("ascii")
    with pytest.raises(ValidationDomainError):
        ReportService._decode_company_logo(payload)
