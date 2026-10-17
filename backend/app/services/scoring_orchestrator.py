"""Punto único de entrada para "Calcular resultados" de un estudio.

Compone `ScoringService` (motor canónico: puntuación por ítem, agregación de
constructos padre a partir de descendientes, bandas y materialización de
variables `CONSTRUCT_SCORE` para analítica genérica) con
`CensopasScoringService` (agregación adicional por unidad organizacional).

Un solo `AnalysisRun` por ejecución: nunca dos corridas independientes que el
usuario deba lanzar por separado desde pestañas distintas. Tanto
`POST /studies/{id}/scoring` como `POST /studies/{id}/censopas/scoring` deben
llamar a `run_canonical_scoring` — ninguno de los dos servicios debe volver a
punturar por su cuenta.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationDomainError
from app.models.analysis import AnalysisRun
from app.schemas.scoring import ScoreRunSummary
from app.services.censopas_service import CensopasScoringService
from app.services.scoring_service import ScoringService


async def run_canonical_scoring(
    session: AsyncSession, study_id: int
) -> tuple[AnalysisRun, ScoreRunSummary]:
    censopas_service = CensopasScoringService(session)

    study = await censopas_service.study_repo.get(study_id)
    if study is None:
        raise NotFoundError(f"Estudio {study_id} no encontrado")
    if study.instrument_version_id is None:
        raise ValidationDomainError(
            "El estudio no tiene una versión de instrumento asociada; no se puede aplicar scoring."
        )

    version = await censopas_service.instrument_repo.get_version_with_instrument(
        study.instrument_version_id
    )
    if version is None:
        raise NotFoundError(f"Versión de instrumento {study.instrument_version_id} no encontrada")

    readiness = await censopas_service.get_readiness(version.id)
    is_censopas = readiness["is_censopas_instrument"]
    if readiness["version_kind"] != "UNKNOWN" and not readiness["ready_for_scoring"]:
        raise ValidationDomainError(
            "La versión CENSOPAS no está lista para ejecutar scoring.",
            readiness=readiness,
        )

    run, summary = await ScoringService(session).run(
        study_id, require_explicit_scoring_rules=is_censopas
    )
    session_units = await censopas_service._load_session_units(study_id)
    if is_censopas or session_units:
        await censopas_service.build_unit_results(study_id, run.id)
    return run, summary
