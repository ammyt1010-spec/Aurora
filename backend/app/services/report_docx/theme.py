"""Paleta corporativa AURORA Professional, tipografía y métricas de página.

Única fuente de verdad para todo HEX/tamaño usado en el renderer — ninguna
otra función de `report_docx` debe declarar un color o un tamaño de fuente
por su cuenta.
"""

from __future__ import annotations

from docx.shared import Mm

COLMENA = {
    "navy": "192C55",
    "teal": "21ABA8",
    "gold": "DDA629",
    "text": "20324A",
    "muted": "63758D",
    "line": "DCE4F0",
    "surface": "F6F8FD",
    "surface_alt": "EBF1FB",
    "green": "1A9F87",
    "yellow": "E6A643",
    "red": "D75E6D",
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

FONT_FAMILY = "Calibri"
