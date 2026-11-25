"""Read-only enterprise audit trail, restricted to the company OWNER/ADMIN."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthorizationError
from app.core.security import get_current_user
from app.models.audit import AuditLog
from app.models.project import Project
from app.models.user import Organization, OrganizationMembership, User
from app.schemas.audit import AuditEventRead, AuditEventsPage

router = APIRouter(prefix="/organizations", tags=["audit"])


@router.get("/{organization_id}/audit-events", response_model=AuditEventsPage)
async def list_enterprise_audit_events(
    organization_id: int,
    limit: int = Query(default=30, ge=1, le=100),
    before_id: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Authorize BEFORE touching logs. A membership in another company or
    # project-level VIEWER access never confers permission to see audit history.
    membership = await session.get(OrganizationMembership, (organization_id, user.id))
    organization = await session.get(Organization, organization_id)
    if (
        membership is None
        or membership.role_code not in {"OWNER", "ADMIN", "TENANT_ADMIN"}
        or organization is None
        or organization.status != "ACTIVE"
    ):
        raise AuthorizationError("No puedes consultar la auditoría de esta empresa.")

    # Legacy project events may not contain organization_id. Include them only
    # if their verified project belongs to the requested company, never by user_id.
    project_ids = select(Project.id).where(Project.organization_id == organization_id)
    scoped_events = or_(
        and_(
            AuditLog.organization_id == organization_id,
            or_(AuditLog.project_id.is_(None), AuditLog.project_id.in_(project_ids)),
        ),
        and_(
            AuditLog.organization_id.is_(None),
            AuditLog.project_id.in_(project_ids),
        ),
    )
    query = select(AuditLog).where(scoped_events)
    if before_id is not None:
        query = query.where(AuditLog.id < before_id)
    events = list((
        await session.execute(
            query.order_by(AuditLog.id.desc()).limit(limit + 1)
        )
    ).scalars().all())
    has_more = len(events) > limit
    page = events[:limit]
    return AuditEventsPage(
        items=[
            AuditEventRead(
                id=event.id, action=event.action, actor_user_id=event.user_id,
                organization_id=event.organization_id,
                project_id=event.project_id, entity_type=event.entity_type,
                entity_id=event.entity_id, created_at=event.created_at,
            )
            for event in page
        ],
        next_before_id=page[-1].id if page and has_more else None,
    )
