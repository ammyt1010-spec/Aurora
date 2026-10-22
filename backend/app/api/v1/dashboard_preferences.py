"""Preferencias de tablero por usuario y empresa: solo disposición, nunca resultados."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.security import get_current_user
from app.models.user import Organization, OrganizationMembership, User

router = APIRouter(prefix="/dashboard-preferences", tags=["dashboard-preferences"])

WIDGET_IDS = frozenset({"summary", "distribution", "ranking", "segments", "actions", "trend"})
DEFAULT_WIDGETS = ["summary", "distribution", "ranking", "segments", "actions", "trend"]
MODES = {"stacked", "heatmap", "cards"}


class DashboardPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    widgets: list[str] = Field(default_factory=lambda: list(DEFAULT_WIDGETS), min_length=1, max_length=6)
    density: str = "compact"
    chart_mode: str = "stacked"

    @staticmethod
    def normalized(payload: "DashboardPreferences") -> "DashboardPreferences":
        if len(set(payload.widgets)) != len(payload.widgets) or any(w not in WIDGET_IDS for w in payload.widgets):
            from app.core.exceptions import ValidationDomainError
            raise ValidationDomainError("La disposición contiene cuadros duplicados o no permitidos.")
        if payload.density not in {"compact", "comfortable"} or payload.chart_mode not in MODES:
            from app.core.exceptions import ValidationDomainError
            raise ValidationDomainError("Modo de tablero no válido.")
        return payload


async def _require_membership(db: AsyncSession, organization_id: int, user_id: int) -> None:
    org = await db.get(Organization, organization_id)
    if org is None:
        raise NotFoundError("Empresa no encontrada.")
    stmt = select(OrganizationMembership).where(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user_id,
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise AuthorizationError("No perteneces a esta organización.")


@router.get("/{organization_id}", response_model=DashboardPreferences)
async def get_preferences(
    organization_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_membership(db, organization_id, user.id)
    layouts = (user.metadata_ or {}).get("aurora_dashboard_layouts") or {}
    saved = layouts.get(str(organization_id))
    if not isinstance(saved, dict):
        return DashboardPreferences()
    try:
        return DashboardPreferences.normalized(DashboardPreferences.model_validate(saved))
    except Exception:
        # Preferencias históricas malformadas no bloquean el acceso al dashboard.
        return DashboardPreferences()


@router.put("/{organization_id}", response_model=DashboardPreferences)
async def save_preferences(
    organization_id: int,
    payload: DashboardPreferences,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_membership(db, organization_id, user.id)
    safe = DashboardPreferences.normalized(payload)
    # Bloqueo de fila: dos pestañas no deben perder actualizaciones de metadata de usuario.
    locked = (await db.execute(select(User).where(User.id == user.id).with_for_update())).scalar_one()
    metadata = dict(locked.metadata_ or {})
    layouts = dict(metadata.get("aurora_dashboard_layouts") or {})
    layouts[str(organization_id)] = safe.model_dump()
    metadata["aurora_dashboard_layouts"] = layouts
    locked.metadata_ = metadata
    await db.commit()
    return safe
