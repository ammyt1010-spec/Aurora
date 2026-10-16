"""Administrative actions and their audit evidence commit together."""
import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.user import User
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_project_membership_lifecycle_records_actor_and_role_without_secrets(session, seed_user, seed_project):
    member = User(email="audited-member@aurora.test", username="audited-member", status="ACTIVE")
    session.add(member)
    await session.commit()
    await session.refresh(member)

    service = ProjectService(session)
    await service.add_member(seed_project, seed_user, member.id, "VIEWER")
    await service.add_member(seed_project, seed_user, member.id, "EDITOR")
    await service.remove_member(seed_project, seed_user, member.id)

    rows = list((
        await session.execute(
            select(AuditLog).where(AuditLog.project_id == seed_project.id)
            .order_by(AuditLog.id)
        )
    ).scalars().all())
    assert [row.action for row in rows] == [
        "PROJECT_MEMBER_ADDED",
        "PROJECT_MEMBER_ROLE_CHANGED",
        "PROJECT_MEMBER_REMOVED",
    ]
    assert all(row.user_id == seed_user.id for row in rows)
    assert all(row.entity_id == member.id for row in rows)
    assert rows[0].after_data == {"role": "VIEWER"}
    assert rows[1].before_data == {"role": "VIEWER"}
    assert rows[2].before_data == {"role": "EDITOR"}
