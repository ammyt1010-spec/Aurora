import pytest

from app.core.exceptions import AuthorizationError
from app.models.project import ProjectMember
from app.models.user import User
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_project_membership_role_matrix(session, seed_project, seed_user):
    viewer = User(email="view@aurora.test", username="view-aurora", status="ACTIVE")
    editor = User(email="edit@aurora.test", username="edit-aurora", status="ACTIVE")
    stranger = User(email="strange@aurora.test", username="strange-aurora", status="ACTIVE")
    session.add_all([viewer, editor, stranger])
    await session.flush()
    session.add_all([
        ProjectMember(project_id=seed_project.id, user_id=viewer.id, role_code="VIEWER", permissions={}),
        ProjectMember(project_id=seed_project.id, user_id=editor.id, role_code="EDITOR", permissions={}),
    ])
    await session.commit()
    svc = ProjectService(session)
    await svc.ensure_access(seed_project, viewer, write=False)
    await svc.ensure_access(seed_project, editor, write=True)
    with pytest.raises(AuthorizationError):
        await svc.ensure_access(seed_project, viewer, write=True)
    with pytest.raises(AuthorizationError):
        await svc.ensure_access(seed_project, stranger, write=False)


@pytest.mark.asyncio
async def test_member_listing_contains_shared_project(session, seed_project, seed_user):
    other = User(email="member@aurora.test", username="member-aurora", status="ACTIVE")
    session.add(other)
    await session.commit()
    await session.refresh(other)
    svc = ProjectService(session)
    await svc.add_member(seed_project, seed_user, other.id, "VIEWER")
    from app.core.pagination import PageParams
    page = await svc.list(PageParams(page=1, page_size=10), other.id)
    assert any(project.id == seed_project.id for project in page.items)
