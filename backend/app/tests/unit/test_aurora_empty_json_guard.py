"""HTTP body guard regression: empty JSON commands are permitted, malformed JSON is not."""
import pytest
from fastapi import HTTPException, Request

from app.core.business_access import require_business_access


def post_request(project_id: int, body: bytes) -> Request:
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    return Request({
        "type": "http", "method": "POST",
        "path": f"/api/v1/projects/{project_id}/scoring",
        "path_params": {"project_id": project_id},
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
    }, receive=receive)


@pytest.mark.asyncio
async def test_empty_json_post_does_not_crash_guard(session, seed_project, seed_user):
    await require_business_access(post_request(seed_project.id, b""), db=session, user=seed_user)


@pytest.mark.asyncio
async def test_malformed_nonempty_json_is_not_silently_ignored(session, seed_project, seed_user):
    with pytest.raises(HTTPException) as raised:
        await require_business_access(post_request(seed_project.id, b'{"survey_id":'), db=session, user=seed_user)
    assert raised.value.status_code == 422


@pytest.mark.asyncio
async def test_empty_json_whitespace_allowed(session, seed_project, seed_user):
    await require_business_access(post_request(seed_project.id, b"  "), db=session, user=seed_user)
