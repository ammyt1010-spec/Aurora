"""Motor estadístico básico (harness §21-23, §33-35, §46, §59).

Ejecuta síncronamente (sin Celery): frecuencias, descriptivos y tablas
cruzadas son computacionalmente triviales. Regresión/clustering/reportes
pesados quedan para Fase 9 con un worker real — no se bloquea el request
HTTP aquí porque no hay nada pesado que ejecutar todavía (harness §3, §34).

Cada ejecución crea un `analysis_run` (PENDING -> RUNNING -> COMPLETED/FAILED)
y persiste resultados estructurados en `analysis_results`, nunca sólo una
imagen (§35, §36).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.analytics.crosstabs import compute_crosstab
from app.analytics.descriptive import compute_descriptive
from app.analytics.frequencies import compute_frequencies
from app.analytics.inferential import (
    compute_chi_square,
    compute_kruskal_wallis,
    compute_mann_whitney,
    compute_spearman,
)
from app.analytics.clustering import compute_kmeans
from app.analytics.regression import compute_logistic_regression
from app.analytics.reliability import compute_reliability
from app.core.exceptions import (
    InsufficientSampleError,
    InvalidAnalysisAssumptionError,
    NotFoundError,
    AuthorizationError,
    UnsupportedAnalysisError,
    ValidationDomainError,
)
from app.models.analysis import AnalysisResult, AnalysisRun
from app.models.analytics_plan import AnalyticsPlanTool, StatisticalTool
from app.models.censopas import ConstructScore
from app.models.construct import Construct
from app.models.response import Response
from app.models.variable import Variable
from app.repositories.analytics import AnalyticsRepository
from app.repositories.studies import StudyRepository
from app.schemas.analytics import (
    AnalysisRunCreate,
    ChiSquareRequest,
    CompareGroupsRequest,
    CorrelationRequest,
    CrosstabRequest,
    DescribeRequest,
    FrequenciesRequest,
    KMeansRequest,
    LogisticRegressionRequest,
    LongitudinalComparisonResponse,
    LongitudinalConstructTrend,
    LongitudinalPoint,
    ReliabilityRequest,
)
from app.services.privacy_service import PrivacyService

_SCALE_LEVELS = ("SCALE",)
_CATEGORICAL_LEVELS = ("NOMINAL", "ORDINAL", "BINARY")
_RANKABLE_LEVELS = ("SCALE", "ORDINAL")


class AnalysisService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AnalyticsRepository(session)
        self.study_repo = StudyRepository(session)

    async def list_methods(self):
        return await self.repo.list_methods()

    async def get_run(self, run_id: int) -> AnalysisRun:
        run = await self.repo.get_run(run_id)
        if run is None:
            raise NotFoundError(f"Analysis run {run_id} no encontrado")
        return run

    async def _require_study(self, study_id: int):
        study = await self.study_repo.get(study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")
        return study

    async def _require_plan_tools(self, study_id: int, tool_codes: list[str]) -> None:
        study = await self._require_study(study_id)
        if study.analytics_plan_id is None:
            return
        stmt = (
            select(StatisticalTool.code)
            .join(AnalyticsPlanTool, AnalyticsPlanTool.tool_id == StatisticalTool.id)
            .where(
                AnalyticsPlanTool.plan_id == study.analytics_plan_id,
                AnalyticsPlanTool.enabled.is_(True),
                StatisticalTool.code.in_(tool_codes),
                StatisticalTool.is_active.is_(True),
            )
        )
        enabled = set((await self.session.execute(stmt)).scalars().all())
        if not enabled:
            raise AuthorizationError(
                f"El plan analítico del estudio no habilita: {', '.join(tool_codes)}."
            )

    async def require_plan_tools(self, study_id: int, tool_codes: list[str]) -> None:
        """Validate a capability for endpoints implemented by another engine."""
        await self._require_plan_tools(study_id, tool_codes)

    async def _load_variable(self, variable_id: int) -> Variable:
        variable = await self.session.get(Variable, variable_id)
        if variable is None:
            raise NotFoundError(f"Variable {variable_id} no encontrada")
        return variable

    async def _numeric_values(self, study_id: int, question_id: int) -> list[float]:
        stmt = select(Response.numeric_value).where(
            Response.study_id == study_id,
            Response.question_id == question_id,
            Response.is_missing.is_(False),
            Response.numeric_value.is_not(None),
        )
        return [float(v) for (v,) in (await self.session.execute(stmt)).all()]

    async def _categorical_values(self, study_id: int, question_id: int) -> list[str]:
        stmt = select(Response.raw_code, Response.text_value).where(
            Response.study_id == study_id,
            Response.question_id == question_id,
            Response.is_missing.is_(False),
        )
        rows = (await self.session.execute(stmt)).all()
        return [raw_code if raw_code is not None else text_value for raw_code, text_value in rows if
                raw_code is not None or text_value is not None]

    async def _latest_likert_scoring_run_id(self, study_id: int) -> int:
        stmt = (
            select(AnalysisRun.id)
            .where(
                AnalysisRun.study_id == study_id,
                AnalysisRun.analysis_type == "LIKERT_SCORING",
                AnalysisRun.status == "COMPLETED",
            )
            .order_by(AnalysisRun.completed_at.desc(), AnalysisRun.id.desc())
        )
        run_id = (await self.session.execute(stmt)).scalars().first()
        if run_id is None:
            raise ValidationDomainError(
                "Primero ejecute el scoring Likert para usar puntajes de constructo."
            )
        return run_id

    async def _construct_values_by_session(
        self, study_id: int, construct_id: int
    ) -> dict[int, float]:
        run_id = await self._latest_likert_scoring_run_id(study_id)
        stmt = select(
            ConstructScore.response_session_id, ConstructScore.score_0_100
        ).where(
            ConstructScore.analysis_run_id == run_id,
            ConstructScore.construct_id == construct_id,
            ConstructScore.score_0_100.is_not(None),
        )
        return {
            session_id: float(value)
            for session_id, value in (await self.session.execute(stmt)).all()
        }

    async def _numeric_values_for_variable(
        self, study_id: int, variable: Variable
    ) -> list[float]:
        if variable.construct_id is not None:
            values = await self._construct_values_by_session(study_id, variable.construct_id)
            return list(values.values())
        if variable.question_id is not None:
            return await self._numeric_values(study_id, variable.question_id)
        return []

    async def _rankable_values_for_variable(
        self, study_id: int, variable: Variable
    ) -> dict[int, float]:
        if variable.construct_id is not None:
            return await self._construct_values_by_session(study_id, variable.construct_id)
        if variable.question_id is not None:
            return await self._rankable_values_by_session(study_id, variable.question_id)
        return {}

    async def _new_run(self, study_id: int, analysis_type: str, parameters: dict, method_code: str | None = None) -> AnalysisRun:
        method = await self.repo.get_method_by_code(method_code) if method_code else None
        run = AnalysisRun(
            study_id=study_id,
            analysis_method_id=method.id if method else None,
            analysis_type=analysis_type,
            parameters=parameters,
            status="PENDING",
        )
        return await self.repo.create_run(run)

    async def _start(self, run: AnalysisRun) -> None:
        run.status = "RUNNING"
        run.started_at = datetime.now(UTC)
        await self.session.flush()

    async def _complete(self, run: AnalysisRun) -> None:
        run.status = "COMPLETED"
        run.completed_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.commit()

    async def _fail(self, run: AnalysisRun, error: Exception) -> None:
        run.status = "FAILED"
        run.completed_at = datetime.now(UTC)
        run.error_message = str(error)
        await self.session.flush()
        await self.session.commit()

    # --- Descriptivos (harness §22, §59) ----------------------------------------

    async def run_descriptive(self, study_id: int, payload: DescribeRequest) -> AnalysisRun:
        await self._require_study(study_id)
        run = await self._new_run(
            study_id, "DESCRIPTIVE", {"variable_ids": payload.variable_ids}, "DESCRIPTIVE"
        )
        await self._start(run)
        try:
            for variable_id in payload.variable_ids:
                variable = await self._load_variable(variable_id)
                if variable.measurement_level not in _SCALE_LEVELS:
                    raise InvalidAnalysisAssumptionError(
                        f"DESCRIPTIVE requiere measurement_level=SCALE; "
                        f"'{variable.code}' es {variable.measurement_level}.",
                        variable_code=variable.code,
                    )
                values = await self._numeric_values_for_variable(study_id, variable)
                stats = compute_descriptive(values)
                await self.repo.add_result(
                    self._build_result(run.id, "DESCRIPTIVE", variable, stats)
                )
            await self._complete(run)
        except Exception as exc:
            await self._fail(run, exc)
            raise
        return await self.get_run(run.id)

    # --- Frecuencias (harness §22, §59) -----------------------------------------

    async def run_frequencies(self, study_id: int, payload: FrequenciesRequest) -> AnalysisRun:
        await self._require_study(study_id)
        run = await self._new_run(
            study_id, "FREQUENCIES", {"variable_ids": payload.variable_ids}, "FREQUENCIES"
        )
        await self._start(run)
        try:
            for variable_id in payload.variable_ids:
                variable = await self._load_variable(variable_id)
                if variable.measurement_level not in _CATEGORICAL_LEVELS:
                    raise InvalidAnalysisAssumptionError(
                        f"FREQUENCIES requiere una variable categórica; "
                        f"'{variable.code}' es {variable.measurement_level}.",
                        variable_code=variable.code,
                    )
                values = await self._categorical_values(study_id, variable.question_id) if variable.question_id else []
                stats = compute_frequencies(values)
                await self.repo.add_result(
                    self._build_result(run.id, "FREQUENCY", variable, stats)
                )
            await self._complete(run)
        except Exception as exc:
            await self._fail(run, exc)
            raise
        return await self.get_run(run.id)

    # --- Tablas cruzadas (harness §23) ------------------------------------------

    async def run_crosstab(self, study_id: int, payload: CrosstabRequest) -> AnalysisRun:
        study = await self._require_study(study_id)
        run = await self._new_run(
            study_id,
            "CROSSTAB",
            {
                "row_variable_id": payload.row_variable_id,
                "column_variable_id": payload.column_variable_id,
                "percentage_mode": payload.percentage_mode,
            },
        )
        await self._start(run)
        try:
            row_var = await self._load_variable(payload.row_variable_id)
            col_var = await self._load_variable(payload.column_variable_id)
            for var in (row_var, col_var):
                if var.measurement_level not in _CATEGORICAL_LEVELS:
                    raise InvalidAnalysisAssumptionError(
                        f"CROSSTAB requiere variables categóricas; "
                        f"'{var.code}' es {var.measurement_level}.",
                        variable_code=var.code,
                    )
            pairs = await self._paired_categorical_values(
                study_id, row_var.question_id, col_var.question_id
            )
            stats = compute_crosstab(pairs, payload.percentage_mode)
            stats = PrivacyService.suppress_crosstab_table(stats, study.min_publishable_n)
            result = self._build_result(run.id, "CROSSTAB", row_var, stats)
            result.result_code = f"{row_var.code}_x_{col_var.code}"
            await self.repo.add_result(result)
            await self._complete(run)
        except Exception as exc:
            await self._fail(run, exc)
            raise
        return await self.get_run(run.id)

    async def _paired_categorical_values(
        self, study_id: int, row_question_id: int, col_question_id: int
    ) -> list[tuple[str, str]]:
        stmt = select(
            Response.response_session_id, Response.question_id, Response.raw_code, Response.text_value
        ).where(
            Response.study_id == study_id,
            Response.question_id.in_([row_question_id, col_question_id]),
            Response.is_missing.is_(False),
        )
        by_session: dict[int, dict[int, str]] = {}
        for session_id, question_id, raw_code, text_value in (await self.session.execute(stmt)).all():
            value = raw_code if raw_code is not None else text_value
            if value is None:
                continue
            by_session.setdefault(session_id, {})[question_id] = value

        return [
            (values[row_question_id], values[col_question_id])
            for values in by_session.values()
            if row_question_id in values and col_question_id in values
        ]

    async def _rankable_values_by_session(self, study_id: int, question_id: int) -> dict[int, float]:
        """Valores numéricos u ordinales codificados como `raw_code` (harness §24)."""
        stmt = select(Response.response_session_id, Response.numeric_value, Response.raw_code).where(
            Response.study_id == study_id,
            Response.question_id == question_id,
            Response.is_missing.is_(False),
        )
        values: dict[int, float] = {}
        for session_id, numeric_value, raw_code in (await self.session.execute(stmt)).all():
            if numeric_value is not None:
                values[session_id] = float(numeric_value)
                continue
            if raw_code is not None:
                try:
                    values[session_id] = float(raw_code)
                except ValueError:
                    continue
        return values

    async def _categorical_values_by_session(self, study_id: int, question_id: int) -> dict[int, str]:
        stmt = select(Response.response_session_id, Response.raw_code, Response.text_value).where(
            Response.study_id == study_id,
            Response.question_id == question_id,
            Response.is_missing.is_(False),
        )
        values: dict[int, str] = {}
        for session_id, raw_code, text_value in (await self.session.execute(stmt)).all():
            value = raw_code if raw_code is not None else text_value
            if value is not None:
                values[session_id] = value
        return values

    # --- Chi-cuadrado (harness §24, §47) ----------------------------------------

    async def run_chi_square(self, study_id: int, payload: ChiSquareRequest) -> AnalysisRun:
        await self._require_plan_tools(study_id, ["CHI_SQUARE"])
        row_var = await self._load_variable(payload.row_variable_id)
        col_var = await self._load_variable(payload.column_variable_id)
        run = await self._new_run(
            study_id,
            "CHI_SQUARE",
            {"row_variable_id": payload.row_variable_id, "column_variable_id": payload.column_variable_id},
            "CHI_SQUARE",
        )
        await self._start(run)
        try:
            for var in (row_var, col_var):
                if var.measurement_level not in _CATEGORICAL_LEVELS:
                    raise InvalidAnalysisAssumptionError(
                        f"CHI_SQUARE requiere variables categóricas; '{var.code}' es {var.measurement_level}.",
                        variable_code=var.code,
                    )
            pairs = await self._paired_categorical_values(study_id, row_var.question_id, col_var.question_id)
            row_values = sorted({r for r, _ in pairs})
            col_values = sorted({c for _, c in pairs})
            if len(row_values) < 2 or len(col_values) < 2:
                raise InvalidAnalysisAssumptionError(
                    "CHI_SQUARE requiere al menos 2 categorías con datos en cada variable."
                )
            table = [[sum(1 for r, c in pairs if r == rv and c == cv) for cv in col_values] for rv in row_values]
            stats_result = compute_chi_square(table)

            await self.repo.add_result(
                AnalysisResult(
                    analysis_run_id=run.id,
                    result_code=f"{row_var.code}_x_{col_var.code}",
                    result_type="CHI_SQUARE",
                    n_valid=stats_result["n"],
                    statistic_value=stats_result["statistic"],
                    degrees_freedom=stats_result["degrees_freedom"],
                    p_value=stats_result["p_value"],
                    effect_size=stats_result["effect_size"],
                    effect_label=stats_result["effect_label"],
                    result_data={**stats_result, "row_values": row_values, "column_values": col_values},
                )
            )
            await self._complete(run)
        except Exception as exc:
            await self._fail(run, exc)
            raise
        return await self.get_run(run.id)

    # --- Comparar grupos: Mann-Whitney / Kruskal-Wallis (harness §24, §47) ------

    async def run_compare_groups(self, study_id: int, payload: CompareGroupsRequest) -> AnalysisRun:
        await self._require_plan_tools(study_id, ["MANN_WHITNEY", "KRUSKAL_WALLIS"])
        dependent_var = await self._load_variable(payload.dependent_variable_id)
        group_var = await self._load_variable(payload.group_variable_id)
        run = await self._new_run(
            study_id,
            "COMPARE_GROUPS",
            {
                "dependent_variable_id": payload.dependent_variable_id,
                "group_variable_id": payload.group_variable_id,
            },
        )
        await self._start(run)
        try:
            if dependent_var.measurement_level not in _RANKABLE_LEVELS:
                raise InvalidAnalysisAssumptionError(
                    f"La variable dependiente debe ser ORDINAL o SCALE; '{dependent_var.code}' "
                    f"es {dependent_var.measurement_level}.",
                    variable_code=dependent_var.code,
                )
            if group_var.measurement_level not in _CATEGORICAL_LEVELS:
                raise InvalidAnalysisAssumptionError(
                    f"La variable de grupo debe ser categórica; '{group_var.code}' "
                    f"es {group_var.measurement_level}.",
                    variable_code=group_var.code,
                )

            dep_values = await self._rankable_values_for_variable(study_id, dependent_var)
            group_values = await self._categorical_values_by_session(study_id, group_var.question_id)

            groups: dict[str, list[float]] = {}
            for session_id, value in dep_values.items():
                if session_id in group_values:
                    groups.setdefault(group_values[session_id], []).append(value)

            distinct_groups = sorted(groups.keys())
            if len(distinct_groups) < 2:
                raise InsufficientSampleError(
                    "Se requieren al menos 2 grupos con datos para comparar."
                )
            if any(len(v) < 2 for v in groups.values()):
                raise InsufficientSampleError("Cada grupo debe tener al menos 2 casos válidos.")

            if len(distinct_groups) == 2:
                stats_result = compute_mann_whitney(groups[distinct_groups[0]], groups[distinct_groups[1]])
                method_code = "MANN_WHITNEY"
                n_valid = stats_result["n1"] + stats_result["n2"]
            else:
                stats_result = compute_kruskal_wallis([groups[g] for g in distinct_groups])
                method_code = "KRUSKAL_WALLIS"
                n_valid = stats_result["n"]

            await self.repo.add_result(
                AnalysisResult(
                    analysis_run_id=run.id,
                    result_code=f"{dependent_var.code}_by_{group_var.code}",
                    result_type=method_code,
                    question_id=dependent_var.question_id,
                    construct_id=dependent_var.construct_id,
                    n_valid=n_valid,
                    statistic_value=stats_result["statistic"],
                    p_value=stats_result["p_value"],
                    effect_size=stats_result["effect_size"],
                    effect_label=stats_result["effect_label"],
                    result_data={**stats_result, "groups": distinct_groups, "method": method_code},
                )
            )
            await self._complete(run)
        except Exception as exc:
            await self._fail(run, exc)
            raise
        return await self.get_run(run.id)

    # --- Correlación: Spearman (harness §24, §47) --------------------------------

    async def run_correlation(self, study_id: int, payload: CorrelationRequest) -> AnalysisRun:
        await self._require_plan_tools(study_id, ["SPEARMAN"])
        var_x = await self._load_variable(payload.variable_x_id)
        var_y = await self._load_variable(payload.variable_y_id)
        run = await self._new_run(
            study_id,
            "SPEARMAN",
            {"variable_x_id": payload.variable_x_id, "variable_y_id": payload.variable_y_id},
            "SPEARMAN",
        )
        await self._start(run)
        try:
            for var in (var_x, var_y):
                if var.measurement_level not in _RANKABLE_LEVELS:
                    raise InvalidAnalysisAssumptionError(
                        f"SPEARMAN requiere variables ORDINAL o SCALE; '{var.code}' es {var.measurement_level}.",
                        variable_code=var.code,
                    )

            x_values = await self._rankable_values_for_variable(study_id, var_x)
            y_values = await self._rankable_values_for_variable(study_id, var_y)
            common = sorted(set(x_values) & set(y_values))
            if len(common) < 3:
                raise InsufficientSampleError(
                    "SPEARMAN requiere al menos 3 pares de datos válidos."
                )

            stats_result = compute_spearman([x_values[s] for s in common], [y_values[s] for s in common])
            await self.repo.add_result(
                AnalysisResult(
                    analysis_run_id=run.id,
                    result_code=f"{var_x.code}_x_{var_y.code}",
                    result_type="SPEARMAN",
                    n_valid=stats_result["n"],
                    statistic_value=stats_result["statistic"],
                    p_value=stats_result["p_value"],
                    effect_size=stats_result["effect_size"],
                    effect_label=stats_result["effect_label"],
                    result_data=stats_result,
                )
            )
            await self._complete(run)
        except Exception as exc:
            await self._fail(run, exc)
            raise
        return await self.get_run(run.id)

    # --- Confiabilidad (harness §26) ---------------------------------------------

    async def run_reliability(self, study_id: int, payload: ReliabilityRequest) -> AnalysisRun:
        await self._require_plan_tools(study_id, list(payload.methods))
        stmt = (
            select(Construct)
            .where(Construct.id == payload.construct_id)
            .options(selectinload(Construct.item_links))
        )
        construct = (await self.session.execute(stmt)).scalar_one_or_none()
        if construct is None:
            raise NotFoundError(f"Constructo {payload.construct_id} no encontrado")

        run = await self._new_run(
            study_id, "RELIABILITY", {"construct_id": payload.construct_id, "methods": payload.methods}
        )
        await self._start(run)
        try:
            if len(construct.item_links) < 2:
                raise InvalidAnalysisAssumptionError(
                    "Se requieren al menos 2 ítems en el constructo para calcular confiabilidad."
                )

            per_item_values = [
                await self._rankable_values_by_session(study_id, link.question_id)
                for link in construct.item_links
            ]
            common_sessions = set(per_item_values[0]).intersection(*per_item_values[1:])
            if len(common_sessions) < 3:
                raise InsufficientSampleError(
                    "Se requieren al menos 3 respondientes con todos los ítems del constructo respondidos."
                )

            ordered_sessions = sorted(common_sessions)
            item_matrix = [[values[s] for values in per_item_values] for s in ordered_sessions]
            reliability = compute_reliability(item_matrix)

            method_values = {
                "CRONBACH_ALPHA": reliability["cronbach_alpha"],
                "MCDONALD_OMEGA": reliability["mcdonald_omega"],
            }
            for method in payload.methods:
                await self.repo.add_result(
                    AnalysisResult(
                        analysis_run_id=run.id,
                        result_code=construct.code,
                        result_type=method,
                        construct_id=construct.id,
                        n_valid=len(ordered_sessions),
                        numeric_value=method_values[method],
                        result_data={
                            "construct_code": construct.code,
                            "n_items": reliability["n_items"],
                            "n_respondents": reliability["n_respondents"],
                            "value": method_values[method],
                        },
                    )
                )
            await self._complete(run)
        except Exception as exc:
            await self._fail(run, exc)
            raise
        return await self.get_run(run.id)

    # --- Avanzado: regresión logística / k-means (Fase 9) ------------------------

    async def run_logistic_regression(
        self, study_id: int, payload: LogisticRegressionRequest
    ) -> AnalysisRun:
        await self._require_plan_tools(study_id, ["LOGISTIC_REGRESSION"])
        outcome_var = await self._load_variable(payload.outcome_variable_id)
        predictor_vars = [await self._load_variable(vid) for vid in payload.predictor_variable_ids]

        run = await self._new_run(
            study_id,
            "LOGISTIC_REGRESSION",
            {
                "outcome_variable_id": payload.outcome_variable_id,
                "predictor_variable_ids": payload.predictor_variable_ids,
            },
            "LOGISTIC_REGRESSION",
        )
        await self._start(run)
        try:
            if outcome_var.measurement_level != "BINARY":
                raise InvalidAnalysisAssumptionError(
                    f"LOGISTIC_REGRESSION requiere una variable de resultado BINARY; "
                    f"'{outcome_var.code}' es {outcome_var.measurement_level}.",
                    variable_code=outcome_var.code,
                )
            for var in predictor_vars:
                if var.measurement_level not in _RANKABLE_LEVELS:
                    raise InvalidAnalysisAssumptionError(
                        f"Los predictores deben ser ORDINAL o SCALE; '{var.code}' es {var.measurement_level}. "
                        "Variables categóricas como predictores no están soportadas todavía.",
                        variable_code=var.code,
                    )

            outcome_raw = await self._categorical_values_by_session(study_id, outcome_var.question_id)
            distinct_outcomes = sorted(set(outcome_raw.values()))
            if len(distinct_outcomes) != 2:
                raise InvalidAnalysisAssumptionError(
                    "La variable de resultado debe tener exactamente 2 categorías con datos."
                )
            outcome_map = {distinct_outcomes[0]: 0, distinct_outcomes[1]: 1}

            predictor_values_by_var = [
                await self._rankable_values_for_variable(study_id, var) for var in predictor_vars
            ]
            common_sessions = set(outcome_raw)
            for values in predictor_values_by_var:
                common_sessions &= set(values)

            if len(common_sessions) < 10:
                raise InsufficientSampleError(
                    "Se requieren al menos 10 casos completos (resultado + todos los predictores)."
                )

            ordered_sessions = sorted(common_sessions)
            predictors_matrix = [
                [values[s] for values in predictor_values_by_var] for s in ordered_sessions
            ]
            outcome_vector = [outcome_map[outcome_raw[s]] for s in ordered_sessions]

            stats_result = compute_logistic_regression(predictors_matrix, outcome_vector)
            stats_result["predictor_codes"] = [v.code for v in predictor_vars]
            stats_result["outcome_labels"] = {"0": distinct_outcomes[0], "1": distinct_outcomes[1]}

            await self.repo.add_result(
                AnalysisResult(
                    analysis_run_id=run.id,
                    result_code=outcome_var.code,
                    result_type="LOGISTIC_REGRESSION",
                    question_id=outcome_var.question_id,
                    n_valid=stats_result["n"],
                    numeric_value=stats_result["pseudo_r_squared"],
                    result_data=stats_result,
                )
            )
            await self._complete(run)
        except Exception as exc:
            await self._fail(run, exc)
            raise
        return await self.get_run(run.id)

    async def run_kmeans(self, study_id: int, payload: KMeansRequest) -> AnalysisRun:
        await self._require_plan_tools(study_id, ["KMEANS"])
        variables = [await self._load_variable(vid) for vid in payload.variable_ids]

        run = await self._new_run(
            study_id, "KMEANS", {"variable_ids": payload.variable_ids, "k": payload.k}, "KMEANS"
        )
        await self._start(run)
        try:
            for var in variables:
                if var.measurement_level not in _RANKABLE_LEVELS:
                    raise InvalidAnalysisAssumptionError(
                        f"KMEANS requiere variables ORDINAL o SCALE; '{var.code}' es {var.measurement_level}.",
                        variable_code=var.code,
                    )

            values_by_var = [
                await self._rankable_values_for_variable(study_id, var) for var in variables
            ]
            common_sessions = set(values_by_var[0])
            for values in values_by_var[1:]:
                common_sessions &= set(values)

            if len(common_sessions) < payload.k * 2:
                raise InsufficientSampleError(
                    f"Se requieren al menos {payload.k * 2} casos completos para {payload.k} clusters."
                )

            ordered_sessions = sorted(common_sessions)
            points = [[values[s] for values in values_by_var] for s in ordered_sessions]
            stats_result = compute_kmeans(points, payload.k)
            stats_result["variable_codes"] = [v.code for v in variables]

            await self.repo.add_result(
                AnalysisResult(
                    analysis_run_id=run.id,
                    result_code="KMEANS",
                    result_type="KMEANS",
                    n_valid=stats_result["n"],
                    numeric_value=stats_result["inertia"],
                    result_data=stats_result,
                )
            )
            await self._complete(run)
        except Exception as exc:
            await self._fail(run, exc)
            raise
        return await self.get_run(run.id)

    # --- Descubrimiento (harness §46) -------------------------------------------

    async def available_methods(self, variable_ids: list[int]) -> list[str]:
        variables = [await self._load_variable(vid) for vid in variable_ids]
        levels = {v.measurement_level for v in variables}

        if len(variables) == 1:
            if levels <= set(_SCALE_LEVELS):
                return ["DESCRIPTIVE"]
            if levels <= set(_CATEGORICAL_LEVELS):
                return ["FREQUENCIES"]
            return []

        if len(variables) == 2:
            if levels <= set(_CATEGORICAL_LEVELS):
                return ["FREQUENCIES", "CROSSTAB", "CHI_SQUARE"]
            if levels <= set(_SCALE_LEVELS) or levels <= set(_RANKABLE_LEVELS):
                return ["DESCRIPTIVE", "SPEARMAN"]
            if levels & set(_RANKABLE_LEVELS) and levels & set(_CATEGORICAL_LEVELS):
                return ["COMPARE_GROUPS"]
            return []

        return []

    # --- Dispatch genérico (harness §34) ----------------------------------------

    async def run_generic(self, study_id: int, payload: AnalysisRunCreate) -> AnalysisRun:
        try:
            return await self._dispatch_generic(study_id, payload)
        except KeyError as exc:
            raise ValidationDomainError(
                f"Falta el parámetro requerido {exc} para analysis_type='{payload.analysis_type}'."
            ) from exc

    async def _dispatch_generic(self, study_id: int, payload: AnalysisRunCreate) -> AnalysisRun:
        analysis_type = payload.analysis_type.upper()
        if analysis_type == "DESCRIPTIVE":
            return await self.run_descriptive(
                study_id, DescribeRequest(variable_ids=payload.parameters.get("variable_ids", []))
            )
        if analysis_type == "FREQUENCIES":
            return await self.run_frequencies(
                study_id, FrequenciesRequest(variable_ids=payload.parameters.get("variable_ids", []))
            )
        if analysis_type == "CROSSTAB":
            return await self.run_crosstab(
                study_id,
                CrosstabRequest(
                    row_variable_id=payload.parameters["row_variable_id"],
                    column_variable_id=payload.parameters["column_variable_id"],
                    percentage_mode=payload.parameters.get("percentage_mode", "COUNT"),
                ),
            )
        if analysis_type == "CHI_SQUARE":
            return await self.run_chi_square(
                study_id,
                ChiSquareRequest(
                    row_variable_id=payload.parameters["row_variable_id"],
                    column_variable_id=payload.parameters["column_variable_id"],
                ),
            )
        if analysis_type in ("COMPARE_GROUPS", "MANN_WHITNEY", "KRUSKAL_WALLIS"):
            return await self.run_compare_groups(
                study_id,
                CompareGroupsRequest(
                    dependent_variable_id=payload.parameters["dependent_variable_id"],
                    group_variable_id=payload.parameters["group_variable_id"],
                ),
            )
        if analysis_type in ("CORRELATION", "SPEARMAN"):
            return await self.run_correlation(
                study_id,
                CorrelationRequest(
                    variable_x_id=payload.parameters["variable_x_id"],
                    variable_y_id=payload.parameters["variable_y_id"],
                ),
            )
        if analysis_type == "RELIABILITY":
            return await self.run_reliability(
                study_id,
                ReliabilityRequest(
                    construct_id=payload.parameters["construct_id"],
                    methods=payload.parameters.get("methods", ["CRONBACH_ALPHA", "MCDONALD_OMEGA"]),
                ),
            )
        if analysis_type == "LOGISTIC_REGRESSION":
            return await self.run_logistic_regression(
                study_id,
                LogisticRegressionRequest(
                    outcome_variable_id=payload.parameters["outcome_variable_id"],
                    predictor_variable_ids=payload.parameters["predictor_variable_ids"],
                ),
            )
        if analysis_type == "KMEANS":
            return await self.run_kmeans(
                study_id,
                KMeansRequest(
                    variable_ids=payload.parameters["variable_ids"],
                    k=payload.parameters.get("k", 2),
                ),
            )
        raise UnsupportedAnalysisError(
            f"Tipo de análisis '{analysis_type}' no soportado todavía.", analysis_type=analysis_type
        )

    @staticmethod
    def _build_result(run_id: int, result_type: str, variable: Variable, stats: dict) -> AnalysisResult:
        return AnalysisResult(
            analysis_run_id=run_id,
            result_code=variable.code,
            result_type=result_type,
            question_id=variable.question_id,
            construct_id=variable.construct_id,
            n_valid=stats.get("n_valid"),
            numeric_value=stats.get("mean"),
            result_data=stats,
        )

    async def get_longitudinal_comparison(
        self, project_id: int, study_ids: list[int] | None = None
    ) -> LongitudinalComparisonResponse:
        from collections import Counter
        from app.models.study import Study
        from app.services.scoring_service import ScoringService

        stmt = select(Study).where(
            Study.project_id == project_id, Study.instrument_version_id.is_not(None)
        )
        if study_ids:
            stmt = stmt.where(Study.id.in_(study_ids))
        stmt = stmt.order_by(Study.start_at.asc().nulls_last(), Study.id.asc())
        studies = list((await self.session.execute(stmt)).scalars().all())

        if not studies:
            return LongitudinalComparisonResponse(
                project_id=project_id,
                total_studies_analyzed=0,
                reference_signature=None,
                constructs=[],
            )

        scoring_service = ScoringService(self.session)
        study_overviews = []
        for study in studies:
            overview = await scoring_service.get_overview(study.id)
            algo = study.algorithm_version or "default"
            sig = f"v:{overview.instrument_version_id or 'none'}|algo:{algo}|barem:{overview.barem_id or 'none'}"
            study_overviews.append((study, overview, sig))

        signatures = [sig for _, _, sig in study_overviews]
        sig_counts = Counter(signatures)
        reference_signature = sig_counts.most_common(1)[0][0] if sig_counts else None

        construct_points: dict[str, dict] = {}
        for study, overview, sig in study_overviews:
            for res in overview.results:
                code = res.construct_code or str(res.construct_id)
                if code not in construct_points:
                    construct_points[code] = {
                        "id": res.construct_id,
                        "code": code,
                        "name": res.construct_name,
                        "type": res.construct_type,
                        "points": [],
                    }
                unfavorable_band = next(
                    (b for b in res.bands if b.classification_code == "UNFAVORABLE"), None
                )
                favorable_band = next(
                    (b for b in res.bands if b.classification_code == "FAVORABLE"), None
                )
                intermediate_band = next(
                    (b for b in res.bands if b.classification_code == "INTERMEDIATE"), None
                )
                # Privacidad: Si está suprimido, no revelar medias, medianas ni porcentajes
                mean_val = res.mean_score if not res.suppressed else None
                median_val = res.median_score if not res.suppressed else None
                unfav_pct = unfavorable_band.pct if (unfavorable_band and not res.suppressed) else None
                fav_pct = favorable_band.pct if (favorable_band and not res.suppressed) else None
                inter_pct = intermediate_band.pct if (intermediate_band and not res.suppressed) else None

                point = LongitudinalPoint(
                    study_id=study.id,
                    study_name=study.name,
                    study_status=study.status,
                    date=study.start_at,
                    n_valid=res.n_valid,
                    mean_score=mean_val,
                    median_score=median_val,
                    unfavorable_pct=unfav_pct,
                    favorable_pct=fav_pct,
                    intermediate_pct=inter_pct,
                    suppressed=res.suppressed,
                    signature=sig,
                )
                construct_points[code]["points"].append(point)

        trends: list[LongitudinalConstructTrend] = []
        notes: list[str] = []

        for code, info in construct_points.items():
            pts = info["points"]
            reasons: list[str] = []
            comparable_pts = [p for p in pts if p.signature == reference_signature and not p.suppressed]

            if any(p.signature != reference_signature for p in pts):
                reasons.append("METHODOLOGICAL_INCOMPATIBILITY_SIGNATURE_MISMATCH")
            if any(p.suppressed for p in pts):
                reasons.append("SUPPRESSED_DUE_TO_PRIVACY_THRESHOLD")

            is_comparable = len(comparable_pts) >= 2 and len(comparable_pts) == len(pts)
            methodological_eq = (len(reasons) == 0) and (len(pts) >= 2)

            delta_unfavorable: float | None = None
            delta_mean: float | None = None
            trend_direction: str | None = None

            if is_comparable:
                first = comparable_pts[0]
                last = comparable_pts[-1]
                if last.unfavorable_pct is not None and first.unfavorable_pct is not None:
                    delta_unfavorable = round(last.unfavorable_pct - first.unfavorable_pct, 4)
                    if delta_unfavorable < -2.0:
                        trend_direction = "IMPROVED"
                    elif delta_unfavorable > 2.0:
                        trend_direction = "DETERIORATED"
                    else:
                        trend_direction = "STABLE"
                if last.mean_score is not None and first.mean_score is not None:
                    delta_mean = round(last.mean_score - first.mean_score, 4)
            else:
                if len(pts) <= 1:
                    trend_direction = "BASELINE"
                    reasons.append("INSUFFICIENT_HISTORICAL_POINTS")
                elif any(p.suppressed for p in pts):
                    trend_direction = "INSUFFICIENT_SAMPLE"
                else:
                    trend_direction = "NOT_COMPARABLE"

            trends.append(
                LongitudinalConstructTrend(
                    construct_id=info["id"],
                    construct_code=info["code"],
                    construct_name=info["name"],
                    construct_type=info["type"],
                    points=pts,
                    is_comparable=is_comparable,
                    delta_unfavorable_pct=delta_unfavorable,
                    delta_mean_score=delta_mean,
                    trend_direction=trend_direction,
                    methodological_equivalence=methodological_eq,
                    incomparability_reasons=reasons,
                )
            )

        return LongitudinalComparisonResponse(
            project_id=project_id,
            total_studies_analyzed=len(studies),
            reference_signature=reference_signature,
            constructs=trends,
        )
