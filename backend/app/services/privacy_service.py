"""PrivacyService (harness §31).

Regla mínima: decide si una celda/grupo puede publicarse según
`study.min_publishable_n`. Debe aplicarse igual en API, dashboard, analytics,
reportes y exports — nunca confiar únicamente en ocultar en frontend (§31).
"""

from __future__ import annotations

import copy


class PrivacyService:
    @staticmethod
    def can_publish_group(n: int, min_publishable_n: int) -> bool:
        return n >= min_publishable_n

    @staticmethod
    def suppress_crosstab_table(stats: dict, min_publishable_n: int) -> dict:
        """Suprime celdas con n < `min_publishable_n` sobre el resultado de
        `compute_crosstab` (E-05, harness §31).

        Incluye supresión secundaria por fila: si en una fila sólo se
        suprimiera una celda, `row_total` permitiría deducirla por resta, así
        que en ese caso se suprime también la celda visible más pequeña de
        la fila. No se aplica supresión secundaria por columna (limitación
        conocida, documentada — fuera de alcance de esta corrección).
        """
        result = copy.deepcopy(stats)
        raw_counts = result.pop("raw_counts")
        for row_entry in result["table"]:
            row = row_entry["row"]
            suppressed_cols = [
                col
                for col in result["column_values"]
                if not PrivacyService.can_publish_group(raw_counts[row][col], min_publishable_n)
            ]
            visible_cols = [col for col in result["column_values"] if col not in suppressed_cols]
            if len(suppressed_cols) == 1 and visible_cols:
                smallest = min(visible_cols, key=lambda col: raw_counts[row][col])
                suppressed_cols.append(smallest)
            for col in suppressed_cols:
                row_entry["cells"][col] = None
            row_entry["suppressed_columns"] = sorted(suppressed_cols)
        # Fail-safe: do not publish marginal totals if they could reconstruct
        # a suppressed cell, including through column-wise subtraction.
        if any(entry.get("suppressed_columns") for entry in result["table"]):
            for entry in result["table"]:
                for key in ("row_total", "total", "n"):
                    if key in entry:
                        entry[key] = None
            for key in ("column_totals", "row_totals", "grand_total", "total"):
                if key in result:
                    result[key] = None
        return result
