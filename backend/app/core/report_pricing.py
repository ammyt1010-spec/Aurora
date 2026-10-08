"""Tarifario AURORA WEB: 20% menos que el comparativo entregado por el usuario.

Importación explícita por el operador; nunca altera cotizaciones emitidas.
"""
METHOD_LABELS = {
    "SUSESO_ISTAS21_BREVE": "SUSESO / ISTAS21 breve",
    "CENSOPAS_CORTA": "CENSOPAS COPSOQ corta",
    "CENSOPAS_MEDIA": "CENSOPAS COPSOQ media",
}
# (método, mínimo de trabajadores, máximo inclusivo, precio PEN o Cotizar)
REFERENCE_WEB_TARIFFS = (
    ("SUSESO_ISTAS21_BREVE", 1, 100, "160.00"),
    ("SUSESO_ISTAS21_BREVE", 101, 300, "240.00"),
    ("SUSESO_ISTAS21_BREVE", 301, 500, "320.00"),
    ("SUSESO_ISTAS21_BREVE", 501, 999, "400.00"),
    ("SUSESO_ISTAS21_BREVE", 1000, 1999, "560.00"),
    ("SUSESO_ISTAS21_BREVE", 2000, None, None),
    ("CENSOPAS_CORTA", 1, 100, "400.00"),
    ("CENSOPAS_CORTA", 101, 300, "600.00"),
    ("CENSOPAS_CORTA", 301, 500, "720.00"),
    ("CENSOPAS_CORTA", 501, 999, "1000.00"),
    ("CENSOPAS_CORTA", 1000, None, None),
    ("CENSOPAS_MEDIA", 1, 100, "560.00"),
    ("CENSOPAS_MEDIA", 101, 300, "920.00"),
    ("CENSOPAS_MEDIA", 301, 500, "1200.00"),
    ("CENSOPAS_MEDIA", 501, 999, "1560.00"),
    ("CENSOPAS_MEDIA", 1000, None, None),
)
