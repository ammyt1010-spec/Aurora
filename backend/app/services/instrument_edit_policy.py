"""Política central de edición de instrumentos (harness §41-42, §56).

Consultada desde todos los servicios de escritura del editor (variables ya
usan su propia regla más simple, ver `variable_service.py`). Nunca se repite
esta lógica inline en los routers (§41).

Reglas de estado de `instrument_version.status`:
    DRAFT               -> edición completa
    TEST                -> edición (con auditoría, registrada por el llamador)
    ACTIVE sin estudio abierto -> cambios controlados
    ACTIVE con estudio OPEN referenciándola -> bloquear cambios estructurales (§42)
    USED / CLOSED / LOCKED -> bloqueado; debe crearse una nueva versión (clone)

Además, un instrumento `is_system=True` (p.ej. CENSOPAS-COPSOQ) sólo es
editable mientras su versión esté en DRAFT o TEST, sin importar lo anterior
(§12, §56): "inspeccionar no significa modificar libremente el núcleo oficial".
"""

from __future__ import annotations

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InstrumentLockedError
from app.models.instrument import Instrument, InstrumentVersion
from app.models.study import Study
from app.schemas.instruments import EditableStatus

_LOCKED_VERSION_STATUSES = ("USED", "CLOSED", "LOCKED")
_SYSTEM_EDITABLE_STATUSES = ("DRAFT", "TEST")
# E-06: el bloqueo por estudio abierto no debe limitarse a versiones ACTIVE —
# una versión DRAFT/TEST referenciada por un estudio OPEN (posible porque
# abrir un estudio no fuerza la transición de la versión a ACTIVE) también
# debe congelarse mientras el estudio siga recibiendo respuestas.
_STRUCTURAL_LOCK_STATUSES = ("ACTIVE", "DRAFT", "TEST", "VALIDATING", "AUTHORIZED")


class InstrumentEditPolicy:
    @staticmethod
    def evaluate(
        instrument: Instrument,
        version: InstrumentVersion,
        *,
        open_study_exists: bool = False,
        closed_study_exists: bool = False,
    ) -> EditableStatus:
        """Chequeo de estado puro, sin acceso a DB (usado en tests y como base)."""
        # Bloqueo retroactivo P0: versiones utilizadas en estudios concluidos/cerrados
        if closed_study_exists:
            return EditableStatus(
                editable=False, reason="EVALUATION_CLOSED_RETROACTIVE_LOCK"
            )

        if getattr(instrument, "status", None) == "LOCKED":
            return EditableStatus(editable=False, reason="INSTRUMENT_LOCKED")

        if version.status in _LOCKED_VERSION_STATUSES:
            return EditableStatus(
                editable=False, reason="VERSION_LOCKED_CREATE_NEW_VERSION"
            )

        if instrument.is_system and version.status not in _SYSTEM_EDITABLE_STATUSES:
            return EditableStatus(editable=False, reason="SYSTEM_INSTRUMENT_LOCKED")

        if version.status in _STRUCTURAL_LOCK_STATUSES and open_study_exists:
            return EditableStatus(editable=False, reason="STUDY_OPEN_STRUCTURAL_LOCK")

        return EditableStatus(editable=True, reason=None)

    @staticmethod
    async def _has_open_study(session: AsyncSession, version_id: int) -> bool:
        stmt = select(
            exists().where(
                Study.instrument_version_id == version_id, Study.status == "OPEN"
            )
        )
        return bool((await session.execute(stmt)).scalar())

    @staticmethod
    async def _has_closed_study(session: AsyncSession, version_id: int) -> bool:
        stmt = select(
            exists().where(
                Study.instrument_version_id == version_id,
                Study.status.in_(("CLOSED", "ARCHIVED")),
            )
        )
        return bool((await session.execute(stmt)).scalar())

    @classmethod
    async def evaluate_async(
        cls, session: AsyncSession, instrument: Instrument, version: InstrumentVersion
    ) -> EditableStatus:
        """Chequeo completo (incluye estudios abiertos y cerrados, harness §42) — usar desde servicios."""
        closed_study = await cls._has_closed_study(session, version.id)
        if closed_study:
            return cls.evaluate(
                instrument, version, closed_study_exists=True
            )

        state = cls.evaluate(instrument, version)
        if not state.editable or version.status not in _STRUCTURAL_LOCK_STATUSES:
            return state

        open_study = await cls._has_open_study(session, version.id)
        return cls.evaluate(instrument, version, open_study_exists=open_study)

    @classmethod
    def require_editable(cls, instrument: Instrument, version: InstrumentVersion) -> None:
        """Variante síncrona (sólo estado), preservada para tests unitarios."""
        cls._raise_if_locked(cls.evaluate(instrument, version))

    @classmethod
    async def require_editable_async(
        cls, session: AsyncSession, instrument: Instrument, version: InstrumentVersion
    ) -> None:
        cls._raise_if_locked(await cls.evaluate_async(session, instrument, version))

    @staticmethod
    def _raise_if_locked(state: EditableStatus) -> None:
        if not state.editable:
            raise InstrumentLockedError(
                "Este instrumento/versión no puede modificarse en su estado actual.",
                editable=False,
                reason=state.reason,
            )

    # Alias semánticos usados desde los distintos servicios de escritura
    # (§41): todos delegan en la misma regla de versión + estudios abiertos.
    can_edit_instrument = require_editable_async
    can_edit_version = require_editable_async
    can_edit_question = require_editable_async
    can_edit_construct = require_editable_async
