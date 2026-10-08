"""Confiabilidad: alfa de Cronbach y omega de McDonald (harness §26). Funciones puras.

`compute_mcdonald_omega` usa una aproximación unifactorial vía el primer
componente principal de la matriz de correlación (no un modelo CFA completo
con estimación robusta) — es una simplificación deliberada, documentada aquí
para no sobre-prometer un análisis factorial confirmatorio que este proyecto
no implementa todavía.
"""

from __future__ import annotations

import statistics

import numpy as np


def compute_cronbach_alpha(item_matrix: list[list[float]]) -> float | None:
    """`item_matrix`: una fila por respondiente, una columna por ítem."""
    if not item_matrix or len(item_matrix) < 2 or len(item_matrix[0]) < 2:
        return None

    k = len(item_matrix[0])
    columns = list(zip(*item_matrix, strict=True))

    item_variances = [statistics.variance(col) for col in columns]
    totals = [sum(row) for row in item_matrix]
    total_variance = statistics.variance(totals)
    if total_variance == 0:
        return None

    return (k / (k - 1)) * (1 - sum(item_variances) / total_variance)


def compute_mcdonald_omega(item_matrix: list[list[float]]) -> float | None:
    if not item_matrix or len(item_matrix[0]) < 2 or len(item_matrix) < 3:
        return None

    data = np.array(item_matrix, dtype=float)
    stds = data.std(axis=0, ddof=1)
    if np.any(stds == 0):
        return None

    corr = np.corrcoef(data, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(corr)
    top_index = int(np.argmax(eigenvalues))
    top_eigenvalue = max(eigenvalues[top_index], 0.0)
    loadings = eigenvectors[:, top_index] * np.sqrt(top_eigenvalue)
    # Orientar las cargas para que la suma sea positiva (evita omega negativo
    # por ambigüedad de signo del autovector).
    if loadings.sum() < 0:
        loadings = -loadings

    sum_loadings_sq = float(loadings.sum()) ** 2
    unique_variances = np.clip(1 - loadings**2, a_min=0.0, a_max=None)
    denominator = sum_loadings_sq + float(unique_variances.sum())
    if denominator == 0:
        return None

    return sum_loadings_sq / denominator


def compute_reliability(item_matrix: list[list[float]]) -> dict:
    n_respondents = len(item_matrix)
    n_items = len(item_matrix[0]) if item_matrix else 0

    return {
        "n_items": n_items,
        "n_respondents": n_respondents,
        "cronbach_alpha": compute_cronbach_alpha(item_matrix),
        "mcdonald_omega": compute_mcdonald_omega(item_matrix),
        "omega_method": "PCA_UNIFACTORIAL_APPROXIMATION",
    }
