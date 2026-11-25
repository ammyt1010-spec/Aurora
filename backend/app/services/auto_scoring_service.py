"""Actualización idempotente de resultados colectivos tras respuestas públicas.

La puntuación se recalcula solo cuando hay suficientes sesiones válidas y una
respuesta nueva posterior a la última corrida. El bloqueo por estudio evita
corridas concurrentes cuando varios trabajadores terminan a la vez.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select, text

from app.core.database import AsyncSessionLocal, engine
from app.models.analysis import AnalysisRun
from app.models.instrument import Instrument, InstrumentVersion
from app.models.response import ResponseSession
from app.models.study import Study
from app.services.scoring_orchestrator import run_canonical_scoring

logger = logging.getLogger(__name__)


async def refresh_scores_for_study(study_id: int) -> None:
    """Tarea posterior al envío: nunca altera ni publica respuestas individuales."""
    lock_key = (0x4155524F << 32) + study_id
    async with engine.connect() as lock_connection:
        if lock_connection.dialect.name == "postgresql":
            await lock_connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key})
            await lock_connection.commit()
        try:
            async with AsyncSessionLocal() as session:
                study = await session.get(Study, study_id)
                if study is None or study.instrument_version_id is None:
                    return
                official_version = (await session.execute(
                    select(InstrumentVersion)
                    .join(Instrument, Instrument.id == InstrumentVersion.instrument_id)
                    .where(
                        InstrumentVersion.id == study.instrument_version_id,
                        Instrument.code == "CENSOPAS_COPSOQ",
                        Instrument.is_system.is_(True),
                    )
                )).scalar_one_or_none()
                if official_version is None:
                    return
                valid_count, newest_response_at = (await session.execute(
                    select(func.count(ResponseSession.id), func.max(ResponseSession.completed_at))
                    .where(
                        ResponseSession.study_id == study_id,
                        ResponseSession.status == "COMPLETED",
                        ResponseSession.validation_status == "VALID",
                    )
                )).one()
                if valid_count < study.min_publishable_n or newest_response_at is None:
                    return
                latest = (await session.execute(
                    select(AnalysisRun)
                    .where(
                        AnalysisRun.study_id == study_id,
                        AnalysisRun.analysis_type == "LIKERT_SCORING",
                        AnalysisRun.status == "COMPLETED",
                    )
                    .order_by(AnalysisRun.completed_at.desc(), AnalysisRun.id.desc())
                    .limit(1)
                )).scalar_one_or_none()
                if latest is not None and latest.completed_at is not None:
                    latest_at = latest.completed_at.replace(tzinfo=None)
                    newest_at = newest_response_at.replace(tzinfo=None)
                    if latest_at >= newest_at:
                        return
                run, _summary = await run_canonical_scoring(session, study_id)
                if run.status != "COMPLETED":
                    logger.error("Scoring del estudio %s terminó en estado %s", study_id, run.status)
                    return
                logger.info("Resultados colectivos CENSOPAS actualizados para estudio %s", study_id)
        except Exception:
            logger.exception("No se pudo actualizar scoring para estudio %s", study_id)
        finally:
            if lock_connection.dialect.name == "postgresql":
                await lock_connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
                await lock_connection.commit()
