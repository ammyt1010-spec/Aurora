"""Scoring CENSOPAS-COPSOQ (harness §27-28). Funciones puras.

Distingue explícitamente `raw_code` (nunca se sobrescribe) de `score_0_100`
(derivado). Este módulo no toca la base de datos — recibe mapas de opciones
ya cargados desde `scoring_rules.parameters` por el llamador.
"""

from __future__ import annotations

SCALE_MIN = 0.0
SCALE_MAX = 100.0


def score_item(raw_code: str | None, option_map: dict[str, float]) -> float | None:
    """Traduce un `raw_code` a `score_0_100` usando el mapa de la regla de scoring.

    Devuelve None si no hay respuesta o el código no está en el mapa (ítem
    excluido del cálculo, no un error — harness §28 paso 3 "validar códigos").
    """
    if raw_code is None:
        return None
    return option_map.get(raw_code)


def apply_direction(score_0_100: float, direction: str | None) -> float:
    """Invierte la polaridad de un ítem REVERSE antes de agregarlo (harness §21 `scoring_direction`)."""
    if direction == "REVERSE":
        return SCALE_MAX - score_0_100
    return score_0_100


def derive_item_values(
    raw_code: str | None,
    option_map: dict[str, float],
    direction: str | None,
) -> tuple[float, float] | None:
    """Produce ``(risk_value, score_0_100)`` sin perder el código crudo.

    Las reglas nuevas deben mapear el código impreso a R (1..5). Para
    compatibilidad, los mapas históricos 0..100 también se aceptan y se
    convierten de vuelta a R antes de aplicar la polaridad.
    """
    mapped = score_item(raw_code, option_map)
    if mapped is None:
        return None
    value = float(mapped)
    # A legacy 0..100 map may legitimately include an interior value 5:
    # interpreting that single response as ordinal category R=5 would
    # incorrectly turn a low score into the maximum risk.
    legacy_100 = any(float(candidate) > 5.0 for candidate in option_map.values())
    if legacy_100 and 0.0 <= value <= 100.0:
        risk_value = 1.0 + value / 25.0
    elif 1.0 <= value <= 5.0:
        risk_value = value
    elif 0.0 <= value <= 100.0:
        risk_value = 1.0 + value / 25.0
    else:
        return None
    if direction == "REVERSE":
        risk_value = 6.0 - risk_value
    score_0_100 = 25.0 * (risk_value - 1.0)
    return risk_value, score_0_100


def aggregate_construct_score(item_scores: list[tuple[float, float, str | None]]) -> float | None:
    """Promedio ponderado de ítems ya orientados (score, weight, direction).

    Devuelve None si no hay ítems con score válido (construct sin datos).
    """
    oriented = [(apply_direction(score, direction), weight) for score, weight, direction in item_scores]
    total_weight = sum(weight for _, weight in oriented)
    if total_weight <= 0:
        return None
    return sum(score * weight for score, weight in oriented) / total_weight
