"""Créditos de evaluación por cuenta, independientes del instrumento."""

from sqlalchemy import func, select

from app.core.exceptions import NotFoundError
from app.models.evaluation_entitlement import EvaluationEntitlement
from app.models.user import User

FREE_EVALUATION_LIMIT = 4


class EvaluationAccessService:
    def __init__(self, session):
        self.session = session

    async def lock_account(self, user_id: int) -> None:
        # El bloqueo dura hasta el commit que crea la evaluación y evita que
        # dos solicitudes simultáneas consuman el cuarto crédito.
        found = (await self.session.execute(
            select(User.id).where(User.id == user_id).with_for_update()
        )).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Cuenta no encontrada.")

    async def trial_status(self, user_id: int) -> dict:
        used = (await self.session.execute(
            select(func.count(EvaluationEntitlement.id)).where(
                EvaluationEntitlement.user_id == user_id,
                EvaluationEntitlement.access_kind == "FREE",
            )
        )).scalar_one()
        return {"limit": FREE_EVALUATION_LIMIT, "used": used, "remaining": max(0, FREE_EVALUATION_LIMIT - used)}

    async def for_study(self, study_id: int, *, lock: bool = False) -> EvaluationEntitlement | None:
        stmt = select(EvaluationEntitlement).where(EvaluationEntitlement.study_id == study_id)
        if lock:
            stmt = stmt.with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()
