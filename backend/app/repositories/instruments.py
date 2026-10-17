from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.instrument import Instrument, InstrumentVersion


class InstrumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, instrument_id: int) -> Instrument | None:
        return await self.session.get(Instrument, instrument_id)

    def list_stmt(
        self,
        project_id: int | None = None,
        discipline: str | None = None,
        status: str | None = None,
        search_query: str | None = None,
    ) -> Select:
        from sqlalchemy import or_

        stmt = select(Instrument)
        if project_id is not None:
            stmt = stmt.where(Instrument.project_id == project_id)
        if discipline is not None and discipline.upper() != "ALL":
            stmt = stmt.where(Instrument.discipline == discipline)
        if status is not None and status.upper() != "ALL":
            stmt = stmt.where(Instrument.status == status)
        if search_query and search_query.strip():
            term = f"%{search_query.strip()}%"
            stmt = stmt.where(
                or_(
                    Instrument.name.ilike(term),
                    Instrument.code.ilike(term),
                    Instrument.author.ilike(term),
                    Instrument.description.ilike(term),
                )
            )
        return stmt.order_by(Instrument.created_at.desc())

    async def create(self, instrument: Instrument) -> Instrument:
        self.session.add(instrument)
        await self.session.flush()
        return instrument

    async def get_version(self, version_id: int) -> InstrumentVersion | None:
        return await self.session.get(InstrumentVersion, version_id)

    async def get_version_with_instrument(self, version_id: int) -> InstrumentVersion | None:
        stmt = (
            select(InstrumentVersion)
            .where(InstrumentVersion.id == version_id)
            .options(selectinload(InstrumentVersion.instrument))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_versions(self, instrument_id: int) -> list[InstrumentVersion]:
        stmt = (
            select(InstrumentVersion)
            .where(InstrumentVersion.instrument_id == instrument_id)
            .order_by(InstrumentVersion.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def create_version(self, version: InstrumentVersion) -> InstrumentVersion:
        self.session.add(version)
        await self.session.flush()
        return version
