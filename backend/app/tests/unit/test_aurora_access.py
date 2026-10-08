"""Focused authorization tests for the professional hardening layer."""
import pytest
from fastapi import Request
from app.core.business_access import require_business_access
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.participant_tokens import create_participant_token, verify_participant_token
from app.models.user import User


def request_for_project(project_id):
    return Request({
        "type": "http", "method": "GET",
        "path": f"/api/v1/projects/{project_id}/studies",
        "path_params": {"project_id": project_id},
        "headers": [], "query_string": b"",
    })


@pytest.mark.asyncio
async def test_guard_denies_other_tenant(session, seed_project, seed_user):
    outsider = User(email="outsider@aurora.test", username="outsider-aurora", status="ACTIVE")
    session.add(outsider)
    await session.commit()
    await session.refresh(outsider)
    with pytest.raises(AuthorizationError):
        await require_business_access(request_for_project(seed_project.id), db=session, user=outsider)
    await require_business_access(request_for_project(seed_project.id), db=session, user=seed_user)


def test_participant_token_is_scoped():
    token = create_participant_token(391)
    verify_participant_token(token, 391)
    with pytest.raises(AuthenticationError):
        verify_participant_token(token, 392)
    with pytest.raises(AuthenticationError):
        verify_participant_token("not-a-token", 391)
