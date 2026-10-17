"""Render del bundle de ReportService a un documento Word (.docx) — documento
editorial maquetado con el design system Colmena (`theme`/`page`/`typography`/
`borders`/`cells`/`tables`/`components`/`charts`), no un Word convencional.

Consume el mismo `bundle` dict que antes sólo se serializaba a JSON
(`ReportService._build_bundle`): estudio, `analysis_results`, `barem_results`
(`StudyResultsOverview` con la lista de `ConstructBaremResult`). No recalcula
nada: sólo formatea lo que el bundle ya trae.
"""

from __future__ import annotations

import io

from docx import Document

from .components import add_footer_band, add_header_band
from .page import configure_page
from .sections import build_document_content
from .typography import register_styles

__all__ = ["render_report_docx"]


def render_report_docx(bundle: dict) -> bytes:
    document = Document()
    configure_page(document)
    register_styles(document)
    config = bundle.get("report_template") or {}
    discipline = str(bundle.get("discipline") or "GENERAL").upper()
    default_header = "AURORA PROFESSIONAL | CENSOPAS-COPSOQ" if bundle.get("is_censopas") else f"AURORA PROFESSIONAL | {discipline}"
    title = config.get("header_title") or default_header
    if not isinstance(title, str):
        title = default_header
    footer = f"AURORA PROFESSIONAL · {discipline} · resultados agregados · privacidad protegida"
    color_map = {
        "aurora-amber": ("543909", "DDA629"),
        "aurora-teal": ("0E4B50", "20A7A4"),
        "aurora-indigo": ("29255F", "635BD6"),
    }
    background, accent = color_map.get(config.get("palette"), color_map["aurora-amber"])
    add_header_band(document, title=title, background=background, accent=accent)
    add_footer_band(document, text=footer)

    build_document_content(document, bundle)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
