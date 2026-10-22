"""Reserva atómica para vistas demo de una sola emisión por cuenta."""
from sqlalchemy import delete, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.exceptions import ConflictError
from app.models.demo_report_usage import DemoReportUsage
from app.models.user import User


async def reserve_demo_usage(session, user_id: int | None) -> bool:
    if not user_id:
        return False
    user = await session.get(User, user_id)
    if not user or not bool((user.metadata_ or {}).get("aurora_demo_one_report")):
        return False
    values = {"user_id": user_id, "status": "RESERVED"}
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        stmt = pg_insert(DemoReportUsage).values(**values).on_conflict_do_nothing(index_elements=["user_id"])
    elif dialect == "sqlite":
        stmt = sqlite_insert(DemoReportUsage).values(**values).on_conflict_do_nothing(index_elements=["user_id"])
    else:
        raise RuntimeError("El control demo requiere PostgreSQL o SQLite.")
    result = await session.execute(stmt)
    if result.rowcount != 1:
        raise ConflictError("Esta cuenta demo ya ha utilizado su única vista de muestra.")
    return True


async def complete_demo_usage(session, user_id: int, report_id: int) -> None:
    await session.execute(
        update(DemoReportUsage).where(
            DemoReportUsage.user_id == user_id, DemoReportUsage.status == "RESERVED"
        ).values(status="COMPLETED", report_id=report_id)
    )


async def release_demo_usage(session, user_id: int) -> None:
    await session.execute(
        delete(DemoReportUsage).where(
            DemoReportUsage.user_id == user_id, DemoReportUsage.status == "RESERVED"
        )
    )
