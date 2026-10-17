"""Motor general de scoring Likert, baremos y resultados de estudio.

El backend es la única fuente de verdad: el frontend nunca recalcula puntajes,
polaridad, cortes, porcentajes ni reglas de privacidad.
"""

from __future__ import annotations

import statistics
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import InsufficientSampleError, NotFoundError, ValidationDomainError
from app.models.analysis import AnalysisRun
from app.models.censopas import Barem, BaremBand, ConstructResult, ConstructScore, ResponseScore
from app.models.construct import Construct, ConstructItem
from app.models.instrument import InstrumentVersion
from app.models.option_set import OptionSet
from app.models.question import Question
from app.models.response import Response, ResponseSession
from app.models.scoring import ScoringRule
from app.models.study import Study
from app.models.variable import Variable
from app.repositories.censopas import CensopasRepository
from app.repositories.instruments import InstrumentRepository
from app.repositories.responses import valid_session_ids
from app.repositories.studies import StudyRepository
from app.analytics.censopas.classification import summarize_trichotomy
from app.analytics.methodology_dispatcher import dispatch_construct_aggregation
from app.services.censopas_methodology import (
    resolve_censopas_methodological_status,
    resolve_official_equivalence_enabled,
)
from app.schemas.scoring import (
    ConstructBaremResult,
    ResultBandCount,
    ScoreRunSummary,
    StudyResultsOverview,
)


ALGORITHM_VERSION = "likert-baremos-v1"


class ScoringService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.study_repo = StudyRepository(session)
        self.censopas_repo = CensopasRepository(session)
        self.instrument_repo = InstrumentRepository(session)

    async def _get_study(self, study_id: int) -> Study:
        stmt = (
            select(Study)
            .where(Study.id == study_id)
            .options(
                selectinload(Study.instrument_version).selectinload(
                    InstrumentVersion.instrument
                )
            )
        )
        study = (await self.session.execute(stmt)).scalar_one_or_none()
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")
        if study.instrument_version_id is None:
            raise ValidationDomainError("El estudio no tiene una versión de instrumento asociada.")
        return study

    async def _load_constructs(self, version_id: int) -> list[Construct]:
        stmt = (
            select(Construct)
            .where(Construct.instrument_version_id == version_id)
            .options(
                selectinload(Construct.item_links)
                .selectinload(ConstructItem.question)
                .selectinload(Question.option_set)
                .selectinload(OptionSet.options)
            )
            .order_by(Construct.sort_order, Construct.id)
        )
        return list((await self.session.execute(stmt)).scalars().unique().all())

    async def _load_responses(self, study_id: int) -> tuple[list[ResponseSession], dict[tuple[int, int], Response]]:
        session_stmt = select(ResponseSession).where(
            ResponseSession.id.in_(valid_session_ids(study_id))
        )
        sessions = list((await self.session.execute(session_stmt)).scalars().all())
        if not sessions:
            return [], {}
        response_stmt = select(Response).where(
            Response.response_session_id.in_([item.id for item in sessions])
        )
        responses = list((await self.session.execute(response_stmt)).scalars().all())
        return sessions, {
            (response.response_session_id, response.question_id): response
            for response in responses
        }

    async def _load_rules(self, version_id: int) -> dict[int, ScoringRule]:
        stmt = select(ScoringRule).where(
            ScoringRule.instrument_version_id == version_id,
            ScoringRule.question_id.is_not(None),
            ScoringRule.status.in_(("DRAFT", "ACTIVE", "VALIDATED")),
        )
        rules = list((await self.session.execute(stmt)).scalars().all())
        return {rule.question_id: rule for rule in rules}

    @staticmethod
    def _normalize(value: float, minimum: float, maximum: float) -> float | None:
        if maximum <= minimum:
            return None
        return ((value - minimum) / (maximum - minimum)) * 100.0

    @classmethod
    def _item_values(
        cls, response: Response, link: ConstructItem, rule: ScoringRule | None
    ) -> tuple[float, float] | None:
        question = link.question
        if not question.is_scored or question.question_type != "LIKERT":
            return None
        if response.is_missing:
            return None

        source_values: list[float] = []
        raw_value: float | None = None
        if rule and rule.parameters.get("map"):
            score_map = {
                str(code): float(value) for code, value in rule.parameters["map"].items()
            }
            if response.raw_code is not None:
                raw_value = score_map.get(response.raw_code)
            source_values = list(score_map.values())
        else:
            active_options = [
                option
                for option in (question.option_set.options if question.option_set else [])
                if option.is_active and option.numeric_value is not None
            ]
            source_values = [float(option.numeric_value) for option in active_options]
            if response.numeric_value is not None:
                raw_value = float(response.numeric_value)
            elif response.raw_code is not None:
                raw_value = next(
                    (
                        float(option.numeric_value)
                        for option in active_options
                        if option.raw_code == response.raw_code
                    ),
                    None,
                )

        if raw_value is None or len(set(source_values)) < 2:
            return None
        minimum, maximum = min(source_values), max(source_values)
        normalized = cls._normalize(raw_value, minimum, maximum)
        if normalized is None:
            return None
        if link.scoring_direction == "REVERSE":
            raw_value = minimum + maximum - raw_value
            normalized = 100.0 - normalized
        return raw_value, normalized

    @staticmethod
    def resolve_effective_item_links(constructs: list[Construct]) -> dict[int, list[ConstructItem]]:
        """Ítems puntuables efectivos por constructo, incluyendo los heredados de
        descendientes (p. ej. una DIMENSION sin `item_links` directos pero con
        SUBDIMENSION hijas que sí los tienen). Reutilizado por
        `CensopasScoringService`/provisioning — no debe duplicarse (harness §21).
        """
        children: dict[int, list[int]] = {}
        direct: dict[int, list[ConstructItem]] = {}
        for construct in constructs:
            direct[construct.id] = [
                link for link in construct.item_links if (link.item_role or "SCORED") == "SCORED"
            ]
            if construct.parent_id is not None:
                children.setdefault(construct.parent_id, []).append(construct.id)

        resolved: dict[int, list[ConstructItem]] = {}

        def collect(construct_id: int, trail: set[int]) -> list[ConstructItem]:
            if construct_id in resolved:
                return resolved[construct_id]
            if construct_id in trail:
                raise ValidationDomainError("La jerarquía de constructos contiene un ciclo.")
            by_question = {link.question_id: link for link in direct.get(construct_id, [])}
            for child_id in children.get(construct_id, []):
                for link in collect(child_id, trail | {construct_id}):
                    by_question.setdefault(link.question_id, link)
            resolved[construct_id] = list(by_question.values())
            return resolved[construct_id]

        for construct in constructs:
            collect(construct.id, set())
        return resolved

    @staticmethod
    def _find_band(score: float, bands: list[BaremBand]) -> BaremBand | None:
        ordered = sorted(bands, key=lambda band: (float(band.min_value), band.severity_order))
        for index, band in enumerate(ordered):
            minimum = float(band.min_value)
            maximum = float(band.max_value)
            if score >= minimum and (score < maximum or index == len(ordered) - 1):
                return band
        return None

    @staticmethod
    def _scoring_config(study: Study) -> dict:
        config = {"missing_policy": "ALLOW_PARTIAL", "min_completion_percent": 80.0}
        config.update((study.instrument_version.config or {}).get("scoring", {}))
        config.update((study.settings or {}).get("scoring", {}))
        return config

    @staticmethod
    def _meets_missing_policy(n_answered: int, n_total: int, config: dict) -> bool:
        if not n_total or not n_answered:
            return False
        policy = config.get("missing_policy", "ALLOW_PARTIAL")
        if policy == "STRICT_COMPLETE":
            return n_answered == n_total
        if policy == "PRORATE_IF_THRESHOLD_MET":
            return (n_answered / n_total) * 100 >= float(
                config.get("min_completion_percent", 80)
            )
        return True

    async def _materialize_construct_variables(
        self, study: Study, constructs: list[Construct]
    ) -> None:
        """Registra una única variable técnica para el puntaje global del proyecto.

        Las puntuaciones permanecen inmutables en ``construct_scores``; la
        variable técnica es la entrada de catálogo que permite a los análisis
        genéricos resolver la serie de la última corrida del estudio.
        """
        stmt = select(Variable).where(Variable.project_id == study.project_id)
        existing = list((await self.session.execute(stmt)).scalars().all())
        by_construct = {
            variable.construct_id: variable
            for variable in existing
            if variable.construct_id is not None
        }
        used_codes = {variable.code for variable in existing}

        for construct in constructs:
            variable = by_construct.get(construct.id)
            if variable is None:
                candidates = [
                    construct.code[:120],
                    f"SCORE_{construct.code}"[:120],
                    f"SCORE_{construct.code}_{construct.id}"[:120],
                ]
                code = next((item for item in candidates if item not in used_codes), None)
                if code is None:
                    raise ValidationDomainError(
                        f"No se pudo generar un código único para el constructo {construct.code}."
                    )
                variable = Variable(project_id=study.project_id, code=code, name=construct.name)
                self.session.add(variable)
                used_codes.add(code)

            variable.study_id = None
            variable.instrument_version_id = study.instrument_version_id
            variable.question_id = None
            variable.construct_id = construct.id
            variable.name = construct.name
            variable.label = f"Puntaje 0–100: {construct.name}"
            variable.variable_type = "CONSTRUCT_SCORE"
            variable.data_type = "DECIMAL"
            variable.measurement_level = "SCALE"
            if variable.role in (None, "NONE", "DESCRIPTIVE"):
                variable.role = "DESCRIPTIVE"
            variable.is_editable = False
            variable.formula = f"CONSTRUCT_SCORE({construct.id})"
            variable.metadata_ = {
                **(variable.metadata_ or {}),
                "source": "construct_scores.score_0_100",
                "construct_code": construct.code,
                "managed_by": "likert-scoring",
                "scale_min": 0,
                "scale_max": 100,
            }

        await self.session.flush()

    async def run(
        self, study_id: int, *, require_explicit_scoring_rules: bool = False
    ) -> tuple[AnalysisRun, ScoreRunSummary]:
        """Ejecuta la puntuación canónica del estudio.

        `require_explicit_scoring_rules`: cuando es True, cualquier ítem sin
        una `ScoringRule` validada falla el scoring en vez de recurrir al
        `numeric_value` del option_set — política obligatoria para CENSOPAS
        (el risk_map validado no es intercambiable con una normalización
        genérica), pero no para instrumentos Likert genéricos que nunca
        necesitaron reglas explícitas.
        """
        study = await self._get_study(study_id)
        instrument_version_id = study.instrument_version_id
        constructs = await self._load_constructs(instrument_version_id)
        links_by_construct = self.resolve_effective_item_links(constructs)
        scored_constructs = [item for item in constructs if links_by_construct[item.id]]
        if not scored_constructs:
            raise ValidationDomainError(
                "El instrumento no tiene ítems Likert puntuables vinculados a constructos."
            )
        sessions, responses = await self._load_responses(study_id)
        if not sessions:
            raise InsufficientSampleError(
                "No hay sesiones COMPLETED con validation_status=VALID para calcular el scoring."
            )
        rules = await self._load_rules(study.instrument_version_id)
        barem = await self.censopas_repo.get_barem(study.barem_id) if study.barem_id else None
        bands_by_construct: dict[int, list[BaremBand]] = {}
        if barem:
            for band in barem.bands:
                bands_by_construct.setdefault(band.construct_id, []).append(band)

        run = AnalysisRun(
            study_id=study_id,
            analysis_type="LIKERT_SCORING",
            engine="PYTHON",
            engine_version="scipy",
            algorithm_version=ALGORITHM_VERSION,
            parameters={
                "instrument_version_id": study.instrument_version_id,
                "barem_id": study.barem_id,
                "scoring": self._scoring_config(study),
            },
            status="RUNNING",
            started_at=datetime.now(UTC),
        )
        self.session.add(run)
        await self.session.flush()

        scores_created = 0
        config = self._scoring_config(study)
        aggregate_values: dict[int, list[tuple[float, str | None]]] = {
            construct.id: [] for construct in scored_constructs
        }
        try:
            if require_explicit_scoring_rules:
                missing_rules: list[dict] = []
                seen_question_ids: set[int] = set()
                for construct in scored_constructs:
                    for link in links_by_construct[construct.id]:
                        if link.question_id in seen_question_ids or link.question_id in rules:
                            continue
                        seen_question_ids.add(link.question_id)
                        missing_rules.append(
                            {
                                "construct_id": construct.id,
                                "construct_code": construct.code,
                                "question_id": link.question_id,
                                "question_code": link.question.code if link.question else None,
                            }
                        )
                if missing_rules:
                    raise ValidationDomainError(
                        "Faltan scoring_rules para uno o más ítems puntuables; cárguelas antes "
                        "de ejecutar el scoring.",
                        missing_scoring_rules=missing_rules,
                    )

            for response_session in sessions:
                for construct in scored_constructs:
                    links = links_by_construct[construct.id]
                    raw_weighted = 0.0
                    normalized_weighted = 0.0
                    total_weight = 0.0
                    n_answered = 0
                    for link in links:
                        response = responses.get((response_session.id, link.question_id))
                        if response is None:
                            continue
                        item_values = self._item_values(response, link, rules.get(link.question_id))
                        if item_values is None:
                            continue
                        raw_value, normalized = item_values
                        weight = float(link.weight)
                        if weight <= 0:
                            continue
                        n_answered += 1
                        total_weight += weight
                        raw_weighted += raw_value * weight
                        normalized_weighted += normalized * weight
                        self.session.add(
                            ResponseScore(
                                response_id=response.id,
                                scoring_rule_id=(
                                    rules[link.question_id].id if link.question_id in rules else None
                                ),
                                risk_value=raw_value,
                                score_0_100=normalized,
                                algorithm_version=ALGORITHM_VERSION,
                                metadata_={
                                    "analysis_run_id": run.id,
                                    "construct_id": construct.id,
                                    "direction": link.scoring_direction or "DIRECT",
                                    "weight": weight,
                                },
                            )
                        )

                    n_total = len(links)
                    completion_pct = round((n_answered / n_total) * 100, 4) if n_total else 0.0
                    valid = self._meets_missing_policy(n_answered, n_total, config)
                    raw_score = raw_weighted / total_weight if valid and total_weight else None
                    score_0_100 = (
                        normalized_weighted / total_weight if valid and total_weight else None
                    )
                    band = (
                        self._find_band(score_0_100, bands_by_construct.get(construct.id, []))
                        if score_0_100 is not None
                        else None
                    )
                    construct_score = ConstructScore(
                        study_id=study_id,
                        analysis_run_id=run.id,
                        response_session_id=response_session.id,
                        construct_id=construct.id,
                        barem_id=barem.id if barem else None,
                        band_id=band.id if band else None,
                        n_answered=n_answered,
                        n_total=n_total,
                        completion_pct=completion_pct,
                        raw_score=raw_score,
                        score_0_100=score_0_100,
                        classification=band.label if band else None,
                        algorithm_version=ALGORITHM_VERSION,
                        metadata_={
                            "missing_policy": config.get("missing_policy"),
                            "classification_code": band.classification_code if band else None,
                        },
                    )
                    self.session.add(construct_score)
                    scores_created += 1
                    if score_0_100 is not None:
                        aggregate_values[construct.id].append(
                            (score_0_100, band.classification_code if band else None)
                        )

            version = study.instrument_version
            instrument = version.instrument if version else None
            discipline = instrument.discipline if instrument else None
            method_code = instrument.method_code if instrument else None
            methodological_rules = version.methodological_rules if version else None

            for construct in scored_constructs:
                values = aggregate_values[construct.id]
                summary = dispatch_construct_aggregation(
                    values,
                    discipline=discipline,
                    method_code=method_code,
                    barem=barem,
                    study_algorithm_version=study.algorithm_version,
                    methodological_rules=methodological_rules,
                )
                meta = {
                    "band_counts": dict(Counter(category for _, category in values if category is not None)),
                    **summary.get("metadata", {}),
                }
                self.session.add(
                    ConstructResult(
                        study_id=study_id,
                        analysis_run_id=run.id,
                        construct_id=construct.id,
                        n_valid=summary["n_valid"],
                        favorable_n=summary["favorable_n"],
                        intermediate_n=summary["intermediate_n"],
                        unfavorable_n=summary["unfavorable_n"],
                        favorable_pct=summary["favorable_pct"],
                        intermediate_pct=summary["intermediate_pct"],
                        unfavorable_pct=summary["unfavorable_pct"],
                        construct_score=summary["construct_score"],
                        classification=summary["classification"],
                        classification_status="BAREMED" if barem else "UNCLASSIFIED",
                        barem_id=barem.id if barem else None,
                        algorithm_version=summary["algorithm_version"],
                        metadata_=meta,
                    )
                )

            catalog_constructs = [
                construct for construct in scored_constructs
                if construct.construct_type == "VARIABLE"
            ]
            if not catalog_constructs:
                catalog_constructs = [
                    construct for construct in scored_constructs
                    if construct.parent_id is None
                ]
            await self._materialize_construct_variables(study, catalog_constructs)

            study.algorithm_version = ALGORITHM_VERSION
            run.status = "COMPLETED"
            run.completed_at = datetime.now(UTC)
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            failed_run = AnalysisRun(
                study_id=study_id,
                analysis_type="LIKERT_SCORING",
                engine="PYTHON",
                algorithm_version=ALGORITHM_VERSION,
                parameters={"instrument_version_id": instrument_version_id},
                status="FAILED",
                started_at=run.started_at,
                completed_at=datetime.now(UTC),
                error_message=str(exc),
            )
            self.session.add(failed_run)
            await self.session.commit()
            raise

        summary = ScoreRunSummary(
            analysis_run_id=run.id,
            study_id=study_id,
            sessions_processed=len(sessions),
            scores_created=scores_created,
            constructs_scored=len(scored_constructs),
            algorithm_version=ALGORITHM_VERSION,
        )
        return run, summary

    async def _latest_run(self, study_id: int) -> AnalysisRun | None:
        stmt = (
            select(AnalysisRun)
            .where(
                AnalysisRun.study_id == study_id,
                AnalysisRun.analysis_type.in_(("LIKERT_SCORING", "CENSOPAS_SCORING")),
                AnalysisRun.status == "COMPLETED",
            )
            .order_by(AnalysisRun.completed_at.desc(), AnalysisRun.id.desc())
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_overview(self, study_id: int) -> StudyResultsOverview:
        study = await self._get_study(study_id)
        latest_run = await self._latest_run(study_id)
        completed_stmt = select(func.count()).select_from(valid_session_ids(study_id).subquery())
        n_completed = int((await self.session.execute(completed_stmt)).scalar_one())
        result_barem_id = (
            latest_run.parameters.get("barem_id") if latest_run is not None else study.barem_id
        )
        barem = (
            await self.censopas_repo.get_barem(result_barem_id) if result_barem_id else None
        )
        official_equivalence_enabled = await resolve_official_equivalence_enabled(
            self.instrument_repo, study.instrument_version_id
        )
        methodological_status = resolve_censopas_methodological_status(
            barem, official_equivalence_enabled
        )
        barem_status = methodological_status["barem_status"]
        official_equivalence = methodological_status["official_equivalence"]
        if latest_run is None:
            return StudyResultsOverview(
                study_id=study.id,
                study_name=study.name,
                study_type=study.study_type,
                instrument_id=study.instrument_id,
                instrument_name=study.instrument_name,
                instrument_version_code=study.instrument_version_code,
                analysis_run_id=None,
                algorithm_version=None,
                instrument_version_id=study.instrument_version_id,
                barem_id=result_barem_id,
                barem_name=barem.name if barem else None,
                barem_status=barem_status,
                official_equivalence=official_equivalence,
                n_completed=n_completed,
                min_publishable_n=study.min_publishable_n,
                results=[],
            )

        score_stmt = (
            select(ConstructScore)
            .where(ConstructScore.analysis_run_id == latest_run.id)
            .options(selectinload(ConstructScore.construct), selectinload(ConstructScore.band))
        )
        scores = list((await self.session.execute(score_stmt)).scalars().all())
        by_construct: dict[int, list[ConstructScore]] = {}
        for score in scores:
            if score.score_0_100 is not None:
                by_construct.setdefault(score.construct_id, []).append(score)

        results: list[ConstructBaremResult] = []
        priority: list[tuple[float, int]] = []
        suppress_groups = study.min_publishable_n > 1 or study.study_type == "CENSO"
        for construct_id, construct_scores in by_construct.items():
            construct = construct_scores[0].construct
            n_valid = len(construct_scores)
            suppressed = suppress_groups and n_valid < study.min_publishable_n
            band_counts = Counter(score.band_id for score in construct_scores)
            known_bands = (
                [band for band in barem.bands if band.construct_id == construct_id] if barem else []
            )
            band_rows: list[ResultBandCount] = []
            weighted_priority = 0.0
            for band in sorted(known_bands, key=lambda item: item.severity_order):
                count = band_counts.get(band.id, 0)
                pct = (count / n_valid) * 100 if n_valid else 0.0
                if band.classification_code == "UNFAVORABLE":
                    weighted_priority += pct
                elif not any(item.classification_code == "UNFAVORABLE" for item in known_bands):
                    maximum_order = max(item.severity_order for item in known_bands)
                    direction = (band.metadata_ or {}).get("direction", "LOWER_BETTER")
                    risk_order = (
                        band.severity_order
                        if direction == "LOWER_BETTER"
                        else maximum_order + 1 - band.severity_order
                    )
                    weighted_priority += pct * risk_order / maximum_order
                band_rows.append(
                    ResultBandCount(
                        band_id=band.id,
                        code=band.code,
                        label=band.label,
                        classification_code=band.classification_code,
                        color_hint=band.color_hint,
                        n=None if suppressed else count,
                        pct=None if suppressed else round(pct, 4),
                        suppressed=suppressed,
                    )
                )
            values = [float(score.score_0_100) for score in construct_scores]
            results.append(
                ConstructBaremResult(
                    construct_id=construct_id,
                    parent_id=construct.parent_id,
                    construct_code=construct.code,
                    construct_name=construct.name,
                    construct_type=construct.construct_type,
                    n_valid=n_valid,
                    suppressed=suppressed,
                    mean_score=None if suppressed else round(statistics.fmean(values), 4),
                    median_score=None if suppressed else round(statistics.median(values), 4),
                    bands=band_rows,
                )
            )
            if not suppressed:
                priority.append((weighted_priority, construct_id))

        ranks = {
            construct_id: rank
            for rank, (_, construct_id) in enumerate(
                sorted(priority, key=lambda item: (-item[0], item[1])), start=1
            )
        }
        for result in results:
            result.priority_rank = ranks.get(result.construct_id)
        results.sort(key=lambda item: (item.priority_rank or 9999, item.construct_id))
        return StudyResultsOverview(
            study_id=study.id,
            study_name=study.name,
            study_type=study.study_type,
            instrument_id=study.instrument_id,
            instrument_name=study.instrument_name,
            instrument_version_code=study.instrument_version_code,
            analysis_run_id=latest_run.id,
            algorithm_version=latest_run.algorithm_version,
            instrument_version_id=study.instrument_version_id,
            barem_id=result_barem_id,
            barem_name=barem.name if barem else None,
            barem_status=barem_status,
            official_equivalence=official_equivalence,
            n_completed=n_completed,
            min_publishable_n=study.min_publishable_n,
            results=results,
        )
