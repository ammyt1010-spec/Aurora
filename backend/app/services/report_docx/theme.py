"""Paleta corporativa AURORA Professional, tipografía y métricas de página.

Única fuente de verdad para todo HEX/tamaño usado en el renderer — ninguna
otra función de `report_docx` debe declarar un color o un tamaño de fuente
por su cuenta.
"""

from __future__ import annotations

from docx.shared import Mm

COLMENA = {
    "navy": "0A1F44",
    "teal": "087F8F",  # Uso con texto blanco; cyan luminoso reservado para acentos\n    "cyan": "00D4D8",\n    "violet": "6366F1",
    "gold": "F59E0B",
    "text": "112441",
    "muted": "64748B",
    "line": "E2E8F0",
    "surface": "F8FAFC",
    "surface_alt": "EDF5FC",
    "green": "10B981",
    "yellow": "F59E0B",
    "red": "EF4444",
    "white": "FFFFFF",
}

PAGE = {
    "width": Mm(210),
    "height": Mm(297),
    "margin_top": Mm(13),
    "margin_bottom": Mm(15),
    "margin_left": Mm(16),
    "margin_right": Mm(16),
    "header_distance": Mm(0),
    "footer_distance": Mm(8),
}

CONTENT_WIDTH_MM = 178.0

FONT = {
    "cover_title": 29,
    "cover_org": 19,
    "cover_subtitle": 11.5,
    "h1": 21,
    "h2": 15,
    "h3": 12,
    "body": 9.5,
    "table": 8,
    "table_header": 8,
    "caption": 7.5,
    "label": 9.5,
}

FONT_FAMILY = "Inter"
