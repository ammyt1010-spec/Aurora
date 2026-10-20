"""Población sintética opcional para probar un informe gratuito de principio a fin."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models.option_set import OptionSetOption
from app.models.project import Project
from app.models.question import Question
from app.models.response import Response, ResponseSelectedOption, ResponseSession
from app.models.study import Study
from app.models.survey import SurveyQuestion
from app.models.user import User
from app.services.project_service import ProjectService
from app.services.scoring_orchestrator import run_canonical_scoring

DEMO_WORKERS = 250


def demo_target(study: Study) -> int:
    invited = (study.settings or {}).get("population_invited")
    try:
        invited_count = int(invited)
    except (TypeError, ValueError):
        invited_count = DEMO_WORKERS
    return max(1, min(DEMO_WORKERS, invited_count))


class DemoPopulationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _study_for_user(self, study_id: int, user: User) -> Study:
        study = await self.session.get(Study, study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")
        project = await self.session.get(Project, study.project_id)
        if project is None:
            raise NotFoundError(f"Proyecto {study.project_id} no encontrado")
        await ProjectService(self.session).ensure_access(project, user, write=True)
        settings = get_settings()
        if settings.environment == "production" or not settings.demo_access_enabled:
            raise AuthorizationError("La muestra sintética solo está disponible en el entorno demo.")
        if (project.metadata_ or {}).get("commercial_tier") != "FREE_REPORT":
            raise AuthorizationError("La muestra sintética solo está disponible para evaluaciones demo nuevas.")
        return study

    async def status(self, study_id: int, user: User) -> dict:
        study = await self._study_for_user(study_id, user)
        session_count = (await self.session.execute(
            select(func.count(ResponseSession.id)).where(ResponseSession.study_id == study_id)
        )).scalar_one()
        answered_count = (await self.session.execute(
            select(func.count(func.distinct(Response.response_session_id)))
            .where(Response.study_id == study_id)
        )).scalar_one()
        settings = study.settings or {}
        return {
            "status": settings.get("demo_seed_status", "AVAILABLE" if answered_count == 0 else "HAS_RESPONSES"),
            "target": demo_target(study),
            "responses": session_count,
            "synthetic": settings.get("demo_seed_status") == "COMPLETED",
            "error": settings.get("demo_seed_error"),
        }

    async def start(self, study_id: int, user: User) -> dict:
        study = await self._study_for_user(study_id, user)
        await self.session.refresh(study, with_for_update=True)
        count = (await self.session.execute(
            select(func.count(Response.id)).where(Response.study_id == study_id)
        )).scalar_one()
        if count:
            raise ConflictError("El estudio ya contiene respuestas; no se pueden mezclar con la muestra sintética.")
        prior = study.settings or {}
        if prior.get("demo_seed_status") == "RUNNING":
            started = prior.get("demo_seed_started_at")
            try:
                recent = datetime.fromisoformat(started) > datetime.now(UTC) - timedelta(minutes=20)
            except (TypeError, ValueError):
                recent = False
            if recent:
                return await self.status(study_id, user)
        study.settings = {
            **prior,
            "demo_seed_status": "RUNNING",
            "demo_seed_started_at": datetime.now(UTC).isoformat(),
            "demo_seed_error": None,
            "synthetic_data": True,
        }
        await self.session.commit()
        return await self.status(study_id, user)

    async def populate(self, study_id: int) -> None:
        study = await self.session.get(Study, study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")
        questions = list((await self.session.execute(
            select(Question)
            .join(SurveyQuestion, SurveyQuestion.question_id == Question.id)
            .where(SurveyQuestion.survey_id == study.survey_id)
            .order_by(SurveyQuestion.sort_order, Question.id)
        )).scalars().all())
        if not questions:
            raise ConflictError("El formulario no tiene preguntas disponibles.")
        option_ids = {q.option_set_id for q in questions if q.option_set_id is not None}
        option_rows = list((await self.session.execute(
            select(OptionSetOption)
            .where(OptionSetOption.option_set_id.in_(option_ids))
            .order_by(OptionSetOption.sort_order, OptionSetOption.id)
        )).scalars().all()) if option_ids else []
        options_by_set: dict[int, list[OptionSetOption]] = {}
        for option in option_rows:
            if option.is_active:
                options_by_set.setdefault(option.option_set_id, []).append(option)

        rng = random.Random(f"aurora-demo-{study_id}")
        target = demo_target(study)
        sessions = [ResponseSession(
            study_id=study_id,
            status="COMPLETED",
            validation_status="VALID",
            completed_at=datetime.now(UTC),
            duration_seconds=rng.randint(360, 1500),
            completion_pct=100,
            metadata_={"synthetic_demo": True},
        ) for _ in range(target)]
        self.session.add_all(sessions)
        await self.session.flush()

        responses: list[Response] = []
        multi: list[tuple[Response, int]] = []
        for worker_index, response_session in enumerate(sessions):
            for question in questions:
                options = options_by_set.get(question.option_set_id, [])
                data = {
                    "study_id": study_id,
                    "response_session_id": response_session.id,
                    "question_id": question.id,
                    "is_missing": False,
                    "metadata_": {"synthetic_demo": True},
                }
                if options:
                    # Un sesgo moderado por cohorte permite explorar diferencias
                    # agregadas sin asignar datos identificables a trabajadores.
                    index = min(len(options) - 1, max(0, int(
                        rng.gauss((worker_index % 5) * (len(options) - 1) / 4, 1.1)
                    )))
                    selected = options[index]
                    data.update(option_id=selected.id, raw_code=selected.raw_code)
                elif question.question_type == "NUMBER":
                    data["numeric_value"] = rng.randint(22, 59)
                elif question.question_type == "BOOLEAN":
                    data["boolean_value"] = rng.choice((True, False))
                else:
                    data["text_value"] = "Respuesta sintética"
                    data["raw_code"] = "DEMO"
                response = Response(**data)
                responses.append(response)
                if options and question.question_type in {"MULTIPLE_CHOICE", "RANKING"}:
                    multi.append((response, selected.id))
        self.session.add_all(responses)
        await self.session.flush()
        if multi:
            self.session.add_all([
                ResponseSelectedOption(response_id=response.id, option_id=option_id)
                for response, option_id in multi
            ])
        await self.session.commit()

        try:
            await run_canonical_scoring(self.session, study_id)
            await self.session.refresh(study)
            study.settings = {
                **(study.settings or {}),
                "demo_seed_status": "COMPLETED",
                "demo_seed_count": target,
                "demo_seed_finished_at": datetime.now(UTC).isoformat(),
            }
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            study = await self.session.get(Study, study_id)
            study.settings = {
                **(study.settings or {}),
                "demo_seed_status": "FAILED",
                "demo_seed_error": f"Respuestas creadas, pero el análisis falló: {exc}",
            }
            await self.session.commit()
            raise

    async def mark_failed(self, study_id: int, exc: Exception) -> None:
        await self.session.rollback()
        study = await self.session.get(Study, study_id)
        if study is None:
            return
        study.settings = {
            **(study.settings or {}),
            "demo_seed_status": "FAILED",
            "demo_seed_error": str(exc),
        }
        await self.session.commit()
