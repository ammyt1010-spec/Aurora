"""Despachador metodológico versionado para scoring y agregación de constructos (A3).

Asegura que instrumentos de distintas disciplinas (Ergonomía, Clima Laboral,
Salud Ocupacional, etc.) no sean forzados indebidamente a tricotomías CENSOPAS
ni etiquetados erróneamente con algoritmos ajenos.

Aplica política 'fail-closed' ante reglas no reconocidas o incompatibles.
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from app.analytics.censopas.classification import (
    BAND_CODE_FAVORABLE,
    BAND_CODE_INTERMEDIATE,
    BAND_CODE_UNFAVORABLE,
    summarize_trichotomy,
)
from app.core.exceptions import ValidationDomainError

# Algoritmos reconocidos por el motor de scoring de AURORA
SUPPORTED_ALGORITHMS = {
    "censopas-v2",
    "likert-baremos-v1",
    "ergonomia-v1",
    "clima_laboral-v1",
    "salud_ocupacional-v1",
    "seguridad_industrial-v1",
    "recursos_humanos-v1",
    "multidisciplinary-v1",
}


def dispatch_construct_aggregation(
    values: list[tuple[float, str | None]],
    *,
    discipline: str | None = None,
    method_code: str | None = None,
    barem: Any | None = None,
    study_algorithm_version: str | None = None,
    methodological_rules: dict | None = None,
) -> dict:
    """Calcula el resumen agregado para un constructo según su metodología.

    `values`: lista de (score_0_100, classification_code o label).
    """
    rules = methodological_rules or {}

    # Comportamiento fail-closed ante algoritmos o reglas requeridas incompatibles
    req_algo = rules.get("required_algorithm")
    if req_algo is not None and req_algo not in SUPPORTED_ALGORITHMS:
        raise ValidationDomainError(
            f"El instrumento especifica un algoritmo metodológico no soportado: '{req_algo}'.",
            required_algorithm=req_algo,
        )

    if rules.get("barem_certified") is True and barem is None:
        raise ValidationDomainError(
            "La metodología del instrumento exige un baremo certificado, pero el estudio no tiene ninguno asociado."
        )

    scores = [s for s, _ in values if s is not None]
    n_valid = len(scores)
    construct_score = round(statistics.mean(scores), 4) if scores else None
    median_score = round(statistics.median(scores), 4) if scores else None

    band_counts = dict(Counter(cat for _, cat in values if cat is not None))

    is_censopas = (
        (discipline or "").upper() == "PSICOSOCIAL"
        or (method_code or "").upper() == "CENSOPAS_COPSOQ"
    )
    has_trichotomy_bands = any(
        code in (BAND_CODE_FAVORABLE, BAND_CODE_INTERMEDIATE, BAND_CODE_UNFAVORABLE)
        for code in band_counts
    )

    # Caso 1: CENSOPAS o baremo con tricotomía explícita
    if is_censopas or has_trichotomy_bands:
        summary = summarize_trichotomy(values)
        algo_ver = study_algorithm_version or req_algo or "censopas-v2"
        return {
            "n_valid": summary["n_valid"],
            "construct_score": summary["construct_score"],
            "median_score": median_score,
            "classification": summary["classification"],
            "favorable_n": summary["favorable_n"],
            "intermediate_n": summary["intermediate_n"],
            "unfavorable_n": summary["unfavorable_n"],
            "favorable_pct": summary["favorable_pct"],
            "intermediate_pct": summary["intermediate_pct"],
            "unfavorable_pct": summary["unfavorable_pct"],
            "algorithm_version": algo_ver,
            "metadata": {
                "methodological_family": "PSICOSOCIAL",
                "algorithm_code": method_code or "CENSOPAS_AGGREGATE",
                "band_counts": band_counts,
            },
        }

    # Caso 2: Metodología Multidisciplinaria (Ergonomía, Clima Laboral, etc.)
    # No forzamos tricotomía CENSOPAS ni inventamos etiquetas
    disc_norm = (discipline or "MULTIDISCIPLINARY").upper()
    algo_ver = study_algorithm_version or req_algo or f"{disc_norm.lower()}-v1"

    # Clasificación predominante basada en las bandas reales del baremo
    most_common = Counter(cat for _, cat in values if cat is not None).most_common(1)
    classification = most_common[0][0] if most_common else None

    # Si el baremo tiene bandas definidas, calcular distribución porcentual exacta
    band_pcts: dict[str, float] = {}
    if n_valid > 0:
        for band_code, count in band_counts.items():
            band_pcts[band_code] = round((count / n_valid) * 100, 2)

    return {
        "n_valid": n_valid,
        "construct_score": construct_score,
        "median_score": median_score,
        "classification": classification,
        "favorable_n": None,
        "intermediate_n": None,
        "unfavorable_n": None,
        "favorable_pct": None,
        "intermediate_pct": None,
        "unfavorable_pct": None,
        "algorithm_version": algo_ver,
        "metadata": {
            "methodological_family": disc_norm,
            "algorithm_code": method_code or f"{disc_norm}_AGGREGATE",
            "band_counts": band_counts,
            "band_percentages": band_pcts,
        },
    }
