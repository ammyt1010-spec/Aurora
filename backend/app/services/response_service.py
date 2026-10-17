from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationDomainError
from app.models.option_set import OptionSetOption
from app.models.question import Question
from app.models.response import Response, ResponseSession, ResponseSessionUnit
from app.models.study import StudyUnit, StudyUnitType
from app.models.survey import SurveyQuestion
from app.repositories.responses import ResponseRepository
from app.repositories.studies import StudyRepository
from app.schemas.responses import (
    ResponseSessionCompleteRequest,
    ResponseSessionProgressRead,
    ResponseUpsert,
)
from app.schemas.studies import ResponseSessionUnitsReplace
from app.services.audit_service import AuditService
from app.services.response_completion_policy import resolve_completion_policy


class ResponseService:
    """Captura de respuestas (harness §16-17). Formato largo: una fila por
    sesión + pregunta; nunca una tabla distinta por survey."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ResponseRepository(session)
        self.study_repo = StudyRepository(session)
        self.audit = AuditService(session)

    async def create_session(self, study_id: int) -> ResponseSession:
        study = await self.study_repo.get(study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")
        if study.status != "OPEN":
            raise ConflictError(
                "El estudio debe estar OPEN para aceptar respuestas.",
                current_status=study.status,
            )
        if study.end_at is not None:
            end_at = study.end_at if study.end_at.tzinfo else study.end_at.replace(tzinfo=UTC)
            if datetime.now(UTC) >= end_at:
                raise ConflictError(
                    "El estudio ya alcanzó su fecha de cierre (end_at).",
                    end_at=str(study.end_at),
                )

        response_session = ResponseSession(study_id=study_id)
        response_session = await self.repo.create_session(response_session)
        await self.session.commit()
        return response_session

    async def _get_session(self, response_session_id: int) -> ResponseSession:
        response_session = await self.repo.get_session(response_session_id)
        if response_session is None:
            raise NotFoundError(f"Sesión de respuesta {response_session_id} no encontrada")
        return response_session

    async def _get_question_in_survey(self, survey_id: int, question_id: int) -> Question:
        stmt = select(Question).join(
            SurveyQuestion, SurveyQuestion.question_id == Question.id
        ).where(
            SurveyQuestion.survey_id == survey_id, SurveyQuestion.question_id == question_id
        )
        question = (await self.session.execute(stmt)).scalar_one_or_none()
        if question is None:
            raise ValidationDomainError(
                f"El ítem {question_id} no pertenece al survey de este estudio."
            )
        return question

    async def _resolve_option_by_id(self, question: Question, option_id: int) -> OptionSetOption:
        if question.option_set_id is None:
            raise ValidationDomainError("El ítem no tiene un conjunto de opciones configurado.")
        if question.question_type in {"MULTIPLE_CHOICE", "RANKING"}:
            raise ValidationDomainError(
                "Este ítem requiere selected_option_ids en lugar de option_id."
            )
        stmt = select(OptionSetOption).where(
            OptionSetOption.id == option_id,
            OptionSetOption.option_set_id == question.option_set_id,
            OptionSetOption.is_active.is_(True),
        )
        option = (await self.session.execute(stmt)).scalar_one_or_none()
        if option is None:
            raise ValidationDomainError("La opción no pertenece al ítem o está inactiva.")
        return option

    async def _resolve_option_by_raw_code(self, question: Question, raw_code: str) -> OptionSetOption:
        stmt = select(OptionSetOption).where(
            OptionSetOption.option_set_id == question.option_set_id,
            OptionSetOption.raw_code == raw_code,
            OptionSetOption.is_active.is_(True),
        )
        option = (await self.session.execute(stmt)).scalar_one_or_none()
        if option is None:
            raise ValidationDomainError(
                f"El código '{raw_code}' no pertenece al catálogo de opciones de este ítem.",
                raw_code=raw_code,
                question_id=question.id,
            )
        return option

    async def _resolve_option(
        self, question: Question, payload: ResponseUpsert
    ) -> OptionSetOption | None:
        """Resuelve la opción de catálogo para el valor escalar de la
        respuesta (E-03): por `option_id` explícito, o por `raw_code` contra
        el `option_set` del ítem cuando este último existe. Ítems sin
        catálogo configurado (texto/numérico libre) no se validan aquí."""
        if payload.option_id is not None:
            return await self._resolve_option_by_id(question, payload.option_id)
        if payload.raw_code is not None and question.option_set_id is not None:
            option = await self._resolve_option_by_raw_code(question, payload.raw_code)
            if payload.numeric_value is not None and (
                option.numeric_value is None
                or float(option.numeric_value) != float(payload.numeric_value)
            ):
                raise ValidationDomainError(
                    "numeric_value no coincide con el valor registrado en el catálogo "
                    "para ese raw_code.",
                    raw_code=payload.raw_code,
                    numeric_value=payload.numeric_value,
                )
            return option
        return None

    async def _validate_multi_options(
        self, question: Question, payload: ResponseUpsert
    ) -> dict[int, OptionSetOption]:
        if payload.selected_option_ids is None:
            return {}

        if question.option_set_id is None:
            raise ValidationDomainError("El ítem no tiene un conjunto de opciones configurado.")
        if question.question_type not in {"MULTIPLE_CHOICE", "RANKING"}:
            raise ValidationDomainError(
                "selected_option_ids sólo es válido para selección múltiple o ranking."
            )

        unique_ids = set(payload.selected_option_ids)
        if len(unique_ids) != len(payload.selected_option_ids):
            raise ValidationDomainError("La respuesta contiene opciones duplicadas.")
        stmt = select(OptionSetOption).where(
            OptionSetOption.id.in_(unique_ids),
            OptionSetOption.option_set_id == question.option_set_id,
            OptionSetOption.is_active.is_(True),
        )
        options = list((await self.session.execute(stmt)).scalars().all())
        options_by_id = {option.id: option for option in options}
        if set(options_by_id) != unique_ids:
            raise ValidationDomainError(
                "Una o más opciones no pertenecen al ítem o están inactivas."
            )
        return options_by_id

    async def replace_session_units(
        self,
        response_session_id: int,
        payload: ResponseSessionUnitsReplace,
    ) -> list[int]:
        response_session = await self._get_session(response_session_id)
        if response_session.status == "COMPLETED":
            raise ConflictError(
                "La sesión ya fue completada; sus unidades organizacionales están congeladas."
            )
        study = await self.study_repo.get(response_session.study_id)
        if study and study.status != "OPEN":
            raise ConflictError(
                f"El estudio no admite modificaciones de asignación organizacional (estado: {study.status}).",
                current_status=study.status,
            )
        unit_ids = list(dict.fromkeys(payload.unit_ids))
        if len(unit_ids) != len(payload.unit_ids):
            raise ValidationDomainError("La asignación contiene unidades duplicadas.")
        units: list[StudyUnit] = []
        if unit_ids:
            stmt = (
                select(StudyUnit)
                .join(
                    StudyUnitType,
                    StudyUnitType.id == StudyUnit.study_unit_type_id,
                )
                .where(
                    StudyUnit.id.in_(unit_ids),
                    StudyUnitType.study_id == response_session.study_id,
                    StudyUnit.is_active.is_(True),
                )
            )
            units = list((await self.session.execute(stmt)).scalars().all())
            if {unit.id for unit in units} != set(unit_ids):
                raise ValidationDomainError(
                    "Una o más unidades no pertenecen al estudio o están inactivas."
                )
            unit_type_ids = {unit.study_unit_type_id for unit in units}
            if len(unit_type_ids) != len(units):
                raise ValidationDomainError(
                    "Sólo se puede asignar una unidad por cada tipo de unidad."
                )
        await self.session.execute(
            delete(ResponseSessionUnit).where(
                ResponseSessionUnit.response_session_id == response_session_id
            )
        )
        self.session.add_all(
            [
                ResponseSessionUnit(
                    response_session_id=response_session_id,
                    study_unit_id=unit_id,
                )
                for unit_id in unit_ids
            ]
        )
        await self.session.commit()
        return unit_ids

    async def upsert_response(
        self, response_session_id: int, question_id: int, payload: ResponseUpsert
    ) -> Response:
        response_session = await self._get_session(response_session_id)
        if response_session.status == "COMPLETED":
            raise ConflictError("La sesión ya fue completada; no admite más respuestas.")

        study = await self.study_repo.get(response_session.study_id)
        if study.status != "OPEN":
            raise ConflictError(
                f"El estudio no admite nuevas respuestas (estado actual: {study.status}).",
                current_status=study.status,
            )
        if study.end_at is not None:
            end_at = study.end_at if study.end_at.tzinfo else study.end_at.replace(tzinfo=UTC)
            if datetime.now(UTC) >= end_at:
                raise ConflictError("El estudio ya alcanzó su fecha de cierre (end_at).")
        question = await self._get_question_in_survey(study.survey_id, question_id)
        selected_option = await self._resolve_option(question, payload)
        await self._validate_multi_options(question, payload)

        response = await self.repo.get_response(response_session_id, question_id)
        if response is None:
            response = Response(
                study_id=response_session.study_id,
                response_session_id=response_session_id,
                question_id=question_id,
            )

        # Cuando la opción se resuelve (por `option_id` o por `raw_code`
        # contra el catálogo), se conservan sus valores canónicos y se fija
        # `option_id` aunque el cliente sólo haya mandado `raw_code` — cierra
        # la trazabilidad raw_code -> option -> numeric_value (E-03).
        response.option_id = selected_option.id if selected_option else payload.option_id
        response.raw_code = selected_option.raw_code if selected_option else payload.raw_code
        response.numeric_value = (
            selected_option.numeric_value if selected_option else payload.numeric_value
        )
        response.text_value = payload.text_value
        response.boolean_value = payload.boolean_value
        response.date_value = payload.date_value
        response.datetime_value = payload.datetime_value
        response.value_jsonb = (
            {"selected_option_ids": payload.selected_option_ids}
            if payload.selected_option_ids is not None
            else None
        )
        response.is_missing = payload.is_missing

        response = await self.repo.add_response(response)
        await self.repo.replace_selected_options(
            response.id, payload.selected_option_ids or []
        )
        if response_session.status == "STARTED":
            response_session.status = "IN_PROGRESS"
        await self.session.commit()
        return response

    async def complete_session(
        self, response_session_id: int, payload: ResponseSessionCompleteRequest
    ) -> ResponseSession:
        response_session = await self._get_session(response_session_id)
        if response_session.status == "COMPLETED":
            return response_session

        study = await self.study_repo.get_with_instrument_version(response_session.study_id)

        total_stmt = select(SurveyQuestion).where(SurveyQuestion.survey_id == study.survey_id)
        total_questions = len((await self.session.execute(total_stmt)).scalars().all())

        responses = await self.repo.list_by_session(response_session_id)
        answered = sum(1 for r in responses if not r.is_missing)

        completion_pct = round((answered / total_questions) * 100, 2) if total_questions else 0.0
        policy = resolve_completion_policy(study)
        # El mínimo absoluto nunca excede el total de ítems del instrumento:
        # de lo contrario un instrumento corto (p.ej. 2 preguntas) nunca
        # podría alcanzar VALID aunque se respondiera el 100%.
        min_answered = min(policy.min_answered_count, total_questions)

        now = datetime.now(UTC)
        response_session.status = "COMPLETED"
        response_session.completed_at = now
        response_session.completion_pct = completion_pct
        if response_session.started_at:
            started_at = response_session.started_at
            if started_at.tzinfo is None:
                # SQLite (tests) no conserva el offset de TIMESTAMPTZ; se
                # asume UTC, consistente con `server_default=func.now()`.
                started_at = started_at.replace(tzinfo=UTC)
            response_session.duration_seconds = int((now - started_at).total_seconds())

        if payload.exclusion_reason:
            response_session.validation_status = "EXCLUDED"
            response_session.exclusion_reason = payload.exclusion_reason
        elif answered == 0:
            response_session.validation_status = "EXCLUDED"
            response_session.exclusion_reason = "Sesión sin respuestas registradas."
        elif answered < min_answered:
            response_session.validation_status = "EXCLUDED"
            response_session.exclusion_reason = (
                f"Solo se respondieron {answered} ítems; se requieren al menos "
                f"{min_answered}."
            )
        elif completion_pct >= policy.min_completion_percent:
            response_session.validation_status = "VALID"
        else:
            response_session.validation_status = "REVIEW"

        await self.session.flush()
        await self.audit.log(
            action="RESPONSE_SESSION_COMPLETED",
            entity_type="response_session",
            entity_id=response_session.id,
        )
        await self.session.commit()
        await self.session.refresh(response_session)
        return response_session

    async def get_session_progress(self, response_session_id: int) -> ResponseSessionProgressRead:
        response_session = await self._get_session(response_session_id)
        study = await self.study_repo.get(response_session.study_id)
        total_stmt = select(SurveyQuestion).where(SurveyQuestion.survey_id == study.survey_id)
        total_questions = len((await self.session.execute(total_stmt)).scalars().all())
        responses = await self.repo.list_by_session(response_session_id)
        answered = sum(1 for r in responses if not r.is_missing)
        completion_pct = round((answered / total_questions) * 100, 2) if total_questions else 0.0
        can_resume = response_session.status != "COMPLETED" and study.status == "OPEN"
        return ResponseSessionProgressRead(
            response_session_id=response_session.id,
            study_id=study.id,
            status=response_session.status,
            validation_status=response_session.validation_status,
            total_questions=total_questions,
            answered_questions=answered,
            completion_pct=completion_pct,
            is_completed=(response_session.status == "COMPLETED"),
            can_resume=can_resume,
        )

    async def list_session_responses(self, response_session_id: int) -> list[Response]:
        await self._get_session(response_session_id)
        return await self.repo.list_by_session(response_session_id)
