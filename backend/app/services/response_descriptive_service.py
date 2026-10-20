from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.descriptive import compute_descriptive
from app.core.exceptions import NotFoundError
from app.models.construct import Construct, ConstructItem
from app.models.option_set import OptionSetOption
from app.models.question import Question
from app.models.response import Response, ResponseSelectedOption, ResponseSession
from app.models.variable import Variable
from app.repositories.studies import StudyRepository
from app.schemas.response_descriptives import (
    NumericDescriptives,
    ResponseDescriptives,
    ResponseDescriptivesGroup,
    ResponseDescriptivesSummary,
    ResponseFrequency,
    ResponseQuestionDescriptives,
)


@dataclass(frozen=True)
class _Group:
    key: str
    label: str
    group_type: str


class ResponseDescriptiveService:
    """Descriptivos directos de respuestas válidas, sin crear analysis_runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.study_repo = StudyRepository(session)

    @staticmethod
    def infer_measurement_level(question_type: str, linked_level: str | None) -> str:
        if linked_level:
            return linked_level
        if question_type in {"LIKERT", "RANKING"}:
            return "ORDINAL"
        if question_type in {"SINGLE_CHOICE", "MULTIPLE_CHOICE"}:
            return "NOMINAL"
        if question_type == "BOOLEAN":
            return "BINARY"
        if question_type == "NUMBER":
            return "SCALE"
        return "TEXT"

    @staticmethod
    def visual_group(
        dimension: Construct | None, short_label: str | None, category: str | None
    ) -> _Group:
        if dimension is not None:
            return _Group(
                key=f"dimension:{dimension.id}",
                label=dimension.name,
                group_type="DIMENSION",
            )
        if short_label and short_label.strip():
            label = short_label.strip()
            return _Group(key=f"topic:{label.casefold()}", label=label, group_type="TOPIC")
        if category and category.strip():
            label = category.strip()
            return _Group(
                key=f"category:{label.casefold()}", label=label, group_type="CATEGORY"
            )
        return _Group(key="ungrouped", label="Sin agrupación", group_type="UNGROUPED")

    @staticmethod
    def _dimension_for_question(
        question_id: int,
        links_by_question: dict[int, list[ConstructItem]],
        constructs_by_id: dict[int, Construct],
    ) -> Construct | None:
        candidates: list[Construct] = []
        for link in links_by_question.get(question_id, []):
            construct = constructs_by_id.get(link.construct_id)
            visited: set[int] = set()
            while construct is not None and construct.id not in visited:
                visited.add(construct.id)
                if construct.construct_type == "DIMENSION":
                    candidates.append(construct)
                    break
                construct = constructs_by_id.get(construct.parent_id)
        if not candidates:
            return None
        return min(
            candidates, key=lambda item: (item.sort_order is None, item.sort_order or 0, item.id)
        )

    @staticmethod
    def _value(response: Response):
        for value in (
            response.numeric_value,
            response.text_value,
            response.raw_code,
            response.boolean_value,
            response.date_value,
            response.datetime_value,
        ):
            if value is not None:
                return value
        return None

    async def get(self, study_id: int) -> ResponseDescriptives:
        study = await self.study_repo.get(study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")
        if study.instrument_version_id is None:
            return ResponseDescriptives(
                study_id=study.id,
                instrument_version_id=None,
                min_publishable_n=study.min_publishable_n,
                summary=ResponseDescriptivesSummary(
                    included_cases=0,
                    question_count=0,
                    answered_cells=0,
                    missing_cells=0,
                    missing_pct=0,
                ),
            )

        questions = list(
            (
                await self.session.execute(
                    select(Question)
                    .where(Question.instrument_version_id == study.instrument_version_id)
                    .order_by(Question.sort_order, Question.id)
                )
            )
            .scalars()
            .all()
        )
        option_set_ids = {q.option_set_id for q in questions if q.option_set_id is not None}
        options_by_set: dict[int, list[OptionSetOption]] = defaultdict(list)
        if option_set_ids:
            option_rows = list(
                (
                    await self.session.execute(
                        select(OptionSetOption)
                        .where(OptionSetOption.option_set_id.in_(option_set_ids))
                        .order_by(
                            OptionSetOption.option_set_id,
                            OptionSetOption.sort_order,
                            OptionSetOption.id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for option in option_rows:
                options_by_set[option.option_set_id].append(option)

        constructs = list(
            (
                await self.session.execute(
                    select(Construct).where(
                        Construct.instrument_version_id == study.instrument_version_id
                    )
                )
            )
            .scalars()
            .all()
        )
        constructs_by_id = {item.id: item for item in constructs}
        links_by_question: dict[int, list[ConstructItem]] = defaultdict(list)
        if constructs:
            links = list(
                (
                    await self.session.execute(
                        select(ConstructItem).where(
                            ConstructItem.construct_id.in_(constructs_by_id)
                        )
                    )
                )
                .scalars()
                .all()
            )
            for link in links:
                if link.item_role != "EXCLUDED":
                    links_by_question[link.question_id].append(link)

        variables = list(
            (
                await self.session.execute(
                    select(Variable).where(
                        Variable.project_id == study.project_id,
                        Variable.question_id.in_([q.id for q in questions]),
                    )
                )
            )
            .scalars()
            .all()
        ) if questions else []
        variable_by_question = {item.question_id: item for item in variables}

        valid_session_ids = list(
            (
                await self.session.execute(
                    select(ResponseSession.id).where(
                        ResponseSession.study_id == study_id,
                        ResponseSession.status == "COMPLETED",
                        ResponseSession.validation_status == "VALID",
                    )
                )
            )
            .scalars()
            .all()
        )
        responses = list(
            (
                await self.session.execute(
                    select(Response).where(
                        Response.study_id == study_id,
                        Response.response_session_id.in_(valid_session_ids),
                    )
                )
            )
            .scalars()
            .all()
        ) if valid_session_ids else []
        responses_by_question: dict[int, list[Response]] = defaultdict(list)
        for response in responses:
            responses_by_question[response.question_id].append(response)

        selected_by_response: dict[int, list[int]] = defaultdict(list)
        if responses:
            selected_rows = (
                await self.session.execute(
                    select(ResponseSelectedOption.response_id, ResponseSelectedOption.option_id)
                    .where(ResponseSelectedOption.response_id.in_([r.id for r in responses]))
                )
            ).all()
            for response_id, option_id in selected_rows:
                selected_by_response[response_id].append(option_id)

        output_questions: list[ResponseQuestionDescriptives] = []
        group_map: dict[str, ResponseDescriptivesGroup] = {}
        answered_cells = 0
        total_cases = len(valid_session_ids)

        for question in questions:
            variable = variable_by_question.get(question.id)
            measurement = self.infer_measurement_level(
                question.question_type, variable.measurement_level if variable else None
            )
            dimension = self._dimension_for_question(
                question.id, links_by_question, constructs_by_id
            )
            group = self.visual_group(dimension, question.short_label, question.category)
            group_read = group_map.setdefault(
                group.key,
                ResponseDescriptivesGroup(
                    key=group.key,
                    label=group.label,
                    group_type=group.group_type,
                ),
            )
            group_read.question_ids.append(question.id)

            question_responses = responses_by_question.get(question.id, [])
            present = [
                response
                for response in question_responses
                if not response.is_missing and self._value(response) is not None
            ]
            if question.question_type in {"MULTIPLE_CHOICE", "RANKING"}:
                present = [
                    response
                    for response in question_responses
                    if not response.is_missing and selected_by_response.get(response.id)
                ]
            valid_n = len({r.response_session_id for r in present})
            answered_cells += valid_n
            option_rows = options_by_set.get(question.option_set_id, [])
            count_by_code: Counter[str] = Counter()
            observed_labels: dict[str, str] = {}
            option_by_id = {option.id: option for option in option_rows}
            if question.question_type in {"MULTIPLE_CHOICE", "RANKING"}:
                for response in present:
                    for option_id in selected_by_response.get(response.id, []):
                        option = option_by_id.get(option_id)
                        if option is not None:
                            count_by_code[option.raw_code] += 1
            else:
                for response in present:
                    code = response.raw_code
                    if code is None and response.option_id in option_by_id:
                        code = option_by_id[response.option_id].raw_code
                    if code is None and measurement in {"NOMINAL", "ORDINAL", "BINARY"}:
                        if response.boolean_value is not None:
                            code = "true" if response.boolean_value else "false"
                            observed_labels[code] = "Sí" if response.boolean_value else "No"
                        elif response.text_value is not None:
                            code = response.text_value
                        elif response.numeric_value is not None:
                            code = str(response.numeric_value)
                    if code is not None:
                        normalized_code = str(code)
                        observed_labels.setdefault(normalized_code, normalized_code)
                        count_by_code[normalized_code] += 1

            frequency_rows: list[ResponseFrequency] = []
            configured_codes: set[str] = set()
            cumulative = 0.0
            for index, option in enumerate(option_rows):
                configured_codes.add(option.raw_code)
                n = count_by_code.get(option.raw_code, 0)
                percentage = round(n / valid_n * 100, 2) if valid_n else 0.0
                if measurement == "ORDINAL":
                    cumulative = round(cumulative + percentage, 2)
                frequency_rows.append(
                    ResponseFrequency(
                        code=option.raw_code,
                        label=option.label,
                        order=option.sort_order if option.sort_order is not None else index,
                        n=n,
                        percentage=percentage,
                        cumulative_percentage=cumulative if measurement == "ORDINAL" else None,
                    )
                )
            for index, (code, n) in enumerate(
                sorted(
                    (
                        (code, n)
                        for code, n in count_by_code.items()
                        if code not in configured_codes
                    ),
                    key=lambda item: (-item[1], item[0]),
                ),
                start=len(frequency_rows),
            ):
                frequency_rows.append(
                    ResponseFrequency(
                        code=code,
                        label=observed_labels.get(code, code),
                        order=index,
                        n=n,
                        percentage=round(n / valid_n * 100, 2) if valid_n else 0.0,
                    )
                )

            numeric = None
            numeric_values = [
                float(response.numeric_value)
                for response in present
                if response.numeric_value is not None
            ]
            if numeric_values and measurement in {"SCALE", "ORDINAL"}:
                numeric = NumericDescriptives(**compute_descriptive(numeric_values))
            # No individual answer distribution is publishable below the
            # study's privacy threshold, even to the company dashboard.
            if valid_n < study.min_publishable_n:
                frequency_rows = []
                numeric = None
            output_questions.append(
                ResponseQuestionDescriptives(
                    question_id=question.id,
                    code=question.code or f"P{question.id}",
                    question_text=question.question_text,
                    short_label=question.short_label,
                    category=question.category,
                    question_type=question.question_type,
                    is_scored=question.is_scored,
                    research_role=question.research_role,
                    measurement_level=measurement,
                    variable_id=variable.id if variable else None,
                    variable_code=variable.code if variable else None,
                    variable_label=(variable.label or variable.name) if variable else None,
                    group_key=group.key,
                    group_label=group.label,
                    group_type=group.group_type,
                    valid_n=valid_n,
                    missing_n=max(total_cases - valid_n, 0),
                    frequencies=frequency_rows,
                    numeric=numeric,
                )
            )

        total_cells = total_cases * len(questions)
        missing_cells = max(total_cells - answered_cells, 0)
        return ResponseDescriptives(
            study_id=study.id,
            instrument_version_id=study.instrument_version_id,
            min_publishable_n=study.min_publishable_n,
            summary=ResponseDescriptivesSummary(
                included_cases=total_cases,
                question_count=len(questions),
                answered_cells=answered_cells,
                missing_cells=missing_cells,
                missing_pct=(
                    round(missing_cells / total_cells * 100, 2) if total_cells else 0.0
                ),
            ),
            groups=list(group_map.values()),
            questions=output_questions,
        )
