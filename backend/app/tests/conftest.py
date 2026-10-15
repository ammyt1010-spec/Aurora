"""Fixtures compartidas.

Los tests usan SQLite en memoria (vía `aiosqlite`) en lugar de Postgres para
no requerir infraestructura externa. Las tablas se crean desde
`Base.metadata` (los modelos ORM de Fase 1+2), remapeando el esquema
`colmena` a `None` porque SQLite no soporta esquemas. Esto NO reemplaza la
migración Alembic real (que sí corre contra Postgres con el SQL completo) —
ver README.md.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.business_access import require_business_access, require_response_access
from app.main import app
from app.models import Base
from app.models.instrument import Instrument, InstrumentVersion
from app.models.project import Project
from app.models.user import User


@pytest_asyncio.fixture
async def engine():
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    ).execution_options(schema_translate_map={"colmena": None})
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    # Existing domain regression tests predate HTTP authentication. They
    # exercise business behavior with an explicitly trusted test client;
    # dedicated security tests execute the guards WITHOUT these overrides.
    app.dependency_overrides[require_business_access] = lambda: None
    app.dependency_overrides[require_response_access] = lambda: None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def _reset_public_rate_limit():
    """`ASGITransport` resuelve `request.client` a un valor fijo para todas
    las requests de todos los tests; como `_buckets` es estado de módulo
    global, sin resetear entre tests la suite queda flaky según el orden de
    ejecución (E-17)."""
    from app.core.rate_limit import _buckets

    _buckets.clear()
    yield
    _buckets.clear()


@pytest_asyncio.fixture
async def seed_user(session: AsyncSession) -> User:
    user = User(email="tester@colmena.dev", username="tester", status="ACTIVE")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seed_project(session: AsyncSession, seed_user: User) -> Project:
    project = Project(
        owner_user_id=seed_user.id,
        name="Tesis de satisfacción académica",
        project_type="ACADEMIC",
        status="DRAFT",
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@pytest_asyncio.fixture
async def seed_instrument_draft(session: AsyncSession) -> tuple[Instrument, InstrumentVersion]:
    instrument = Instrument(name="Escala propia", is_system=False, status="DRAFT")
    session.add(instrument)
    await session.flush()

    version = InstrumentVersion(
        instrument_id=instrument.id,
        version_code="V1",
        version_name="Versión 1",
        status="DRAFT",
    )
    session.add(version)
    await session.commit()
    await session.refresh(instrument)
    await session.refresh(version)
    return instrument, version


@pytest_asyncio.fixture
async def seed_censopas_locked(session: AsyncSession) -> tuple[Instrument, InstrumentVersion]:
    instrument = Instrument(
        code="CENSOPAS_COPSOQ", name="CENSOPAS-COPSOQ", is_system=True, status="ACTIVE"
    )
    session.add(instrument)
    await session.flush()

    version = InstrumentVersion(
        instrument_id=instrument.id,
        version_code="SHORT",
        version_name="Versión corta",
        status="ACTIVE",
    )
    session.add(version)
    await session.commit()
    await session.refresh(instrument)
    await session.refresh(version)
    return instrument, version
