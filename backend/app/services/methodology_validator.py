"""Engine de validación metodológica para instrumentos multidisciplinarios (PR #13).

Valida estructura psicométrica/metodológica, dimensiones, subdimensiones, reactivos,
escalas de respuesta, ponderaciones, reglas de puntuación y baremos.
Permite certificar si una versión de instrumento cuenta con configuración suficiente
para ser autorizada y comercializada.
"""
from __future__ import annotations

from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.construct import Construct, ConstructItem
from app.models.instrument import Instrument, InstrumentVersion
from app.models.option_set import OptionSet
from app.models.question import Question
from app.schemas.instruments import MethodologicalValidationResult


class MethodologyValidator:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def validate_version(
        self, version_id: int, *, persist_metrics: bool = True
    ) -> MethodologicalValidationResult:
        """Audita exhaustivamente la estructura psicométrica y de baremación de una versión."""
        stmt = (
            select(InstrumentVersion)
            .where(InstrumentVersion.id == version_id)
            .options(
                selectinload(InstrumentVersion.instrument),
                selectinload(InstrumentVersion.questions)
                .selectinload(Question.option_set)
                .selectinload(OptionSet.options),
                selectinload(InstrumentVersion.constructs),
            )
        )
        version = (await self.session.execute(stmt)).scalar_one_or_none()
        if version is None:
            raise ValueError(f"Versión de instrumento {version_id} no encontrada.")

        errors: list[str] = []
        warnings: list[str] = []

        questions: list[Question] = version.questions or []
        constructs: list[Construct] = version.constructs or []

        # 1. Validación de Reactivos (Preguntas / Ítems)
        total_questions = len(questions)
        if total_questions == 0:
            errors.append("El instrumento no contiene reactivos ni preguntas registradas.")

        scored_questions = [q for q in questions if getattr(q, "is_scored", True)]
        unassigned_questions = 0

        # Cargar mapeo de ítems a constructos si existen
        construct_item_stmt = select(ConstructItem.question_id).join(Construct).where(
            Construct.instrument_version_id == version_id
        )
        assigned_question_ids = set((await self.session.execute(construct_item_stmt)).scalars().all())

        for q in questions:
            # Validar escala de respuesta
            if getattr(q, "question_type", "SINGLE_CHOICE") in {"SINGLE_CHOICE", "LIKERT", "MULTIPLE_CHOICE"}:
                if not q.option_set_id or q.option_set is None:
                    errors.append(f"El reactivo '{q.code or q.id}' carece de escala de opciones (option_set).")
                else:
                    options = getattr(q.option_set, "options", [])
                    if len(options) < 2:
                        errors.append(
                            f"La escala del reactivo '{q.code or q.id}' debe tener al menos 2 opciones de respuesta."
                        )

            # Validar ponderación / pesos
            weight = getattr(q, "weight", 1.0)
            if weight is not None and weight < 0:
                errors.append(f"El reactivo '{q.code or q.id}' tiene una ponderación negativa ({weight}).")

            if q.id not in assigned_question_ids and not getattr(q, "research_role", None):
                unassigned_questions += 1

        if total_questions > 0 and unassigned_questions == total_questions:
            warnings.append("Ningún reactivo está formalmente asociado a dimensiones o roles metodológicos.")

        # 2. Validación de Dimensiones y Subdimensiones
        dimensions = [c for c in constructs if getattr(c, "construct_type", "").upper() in {"DIMENSION", "FACTOR"}]
        subdimensions = [c for c in constructs if getattr(c, "construct_type", "").upper() == "SUBDIMENSION"]

        dimension_count = len(dimensions)
        subdimension_count = len(subdimensions)

        if total_questions > 0 and dimension_count == 0 and len(constructs) == 0:
            warnings.append("No se han definido dimensiones ni factores estructurados para el instrumento.")

        # 3. Validación de Reglas de Puntuación y Baremos
        rules = version.methodological_rules or {}
        config = version.config or {}

        has_scoring_rules = bool(rules.get("scoring_rules") or config.get("scoring_rules") or rules.get("barems") or config.get("barem_matrix"))
        cutoffs = rules.get("cutoffs") or config.get("cutoffs") or rules.get("risk_levels")

        if not has_scoring_rules and scored_questions:
            # Si no hay reglas explícitas en json, verificar si al menos hay baremos o lógica implícita
            if not cutoffs and not config.get("censopas_version_kind"):
                warnings.append("No se han configurado reglas de puntuación o baremos de corte para interpretar los resultados.")

        # Determinación de validez
        is_valid = len(errors) == 0 and total_questions > 0

        # Scoring status: CONFIGURED, PARTIAL, NOT_CONFIGURED
        if is_valid and (has_scoring_rules or cutoffs or config.get("censopas_version_kind")):
            new_scoring_status = "CONFIGURED"
        elif is_valid:
            new_scoring_status = "PARTIAL"
        else:
            new_scoring_status = "NOT_CONFIGURED"

        metrics = {
            "total_questions": total_questions,
            "scored_questions": len(scored_questions),
            "dimension_count": dimension_count,
            "subdimension_count": subdimension_count,
            "has_scoring_rules": has_scoring_rules,
            "has_cutoffs": bool(cutoffs),
            "unassigned_items": unassigned_questions,
        }

        if persist_metrics:
            version.total_questions = total_questions
            version.dimension_count = dimension_count
            version.subdimension_count = subdimension_count
            version.scoring_status = new_scoring_status
            version.validation_notes = (
                f"Validación metodológica ejecutada: {'Aprobada' if is_valid else 'Con observaciones'}. "
                f"Errores: {len(errors)}, Advertencias: {len(warnings)}."
            )
            await self.session.flush()

        return MethodologicalValidationResult(
            version_id=version.id,
            version_code=version.version_code,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            metrics=metrics,
            status=version.status,
            scoring_status=new_scoring_status,
        )
