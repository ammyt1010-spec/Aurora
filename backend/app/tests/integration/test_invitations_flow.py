"""E-17: token de invitación de un solo uso, opt-in por estudio
(`Study.requires_invitation`)."""

from httpx import AsyncClient

from app.core.security import create_access_token


async def _build_study(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft, *, requires_invitation: bool
) -> dict:
    _instrument, version = seed_instrument_draft
    await client.post(
        f"/api/v1/instrument-versions/{version.id}/items",
        json={"code": "P1", "question_text": "P1", "question_type": "NUMBER"},
    )
    survey = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/surveys/from-instrument",
            json={
                "created_by_user_id": seed_user.id,
                "instrument_version_id": version.id,
                "name": "Encuesta invitaciones",
            },
        )
    ).json()
    study = (
        await client.post(
            f"/api/v1/projects/{seed_project.id}/studies",
            json={
                "survey_id": survey["id"],
                "name": "Estudio invitaciones",
                "study_type": "CUSTOM",
                "requires_invitation": requires_invitation,
            },
        )
    ).json()
    assert study["requires_invitation"] is requires_invitation
    await client.post(f"/api/v1/studies/{study['id']}/open")
    return study


async def test_public_session_requires_invitation_when_enabled(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study = await _build_study(
        client, seed_user, seed_project, seed_instrument_draft, requires_invitation=True
    )

    no_token_resp = await client.post(
        f"/api/v1/public/studies/{study['public_id']}/response-sessions"
    )
    assert no_token_resp.status_code == 404, no_token_resp.text
    assert no_token_resp.json()["error_code"] == "PUBLIC_RESOURCE_UNAVAILABLE"

    issue_resp = await client.post(
        f"/api/v1/studies/{study['id']}/invitations", json={"count": 1}
    )
    assert issue_resp.status_code == 201, issue_resp.text
    tokens = issue_resp.json()["tokens"]
    assert len(tokens) == 1
    token = tokens[0]

    summary_resp = await client.get(f"/api/v1/studies/{study['id']}/invitations")
    assert summary_resp.json() == {"total": 1, "pending": 1, "consumed": 0, "expired": 0}

    ok_resp = await client.post(
        f"/api/v1/public/studies/{study['public_id']}/response-sessions",
        json={"invitation_token": token},
    )
    assert ok_resp.status_code == 201, ok_resp.text

    summary_after_resp = await client.get(f"/api/v1/studies/{study['id']}/invitations")
    assert summary_after_resp.json() == {"total": 1, "pending": 0, "consumed": 1, "expired": 0}

    reuse_resp = await client.post(
        f"/api/v1/public/studies/{study['public_id']}/response-sessions",
        json={"invitation_token": token},
    )
    assert reuse_resp.status_code == 404, reuse_resp.text
    assert reuse_resp.json()["error_code"] == "PUBLIC_RESOURCE_UNAVAILABLE"


async def test_public_session_ignores_invitation_when_not_required(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study = await _build_study(
        client, seed_user, seed_project, seed_instrument_draft, requires_invitation=False
    )

    resp = await client.post(f"/api/v1/public/studies/{study['public_id']}/response-sessions")
    assert resp.status_code == 201, resp.text


async def test_invitation_issuance_is_rejected_for_non_invitation_study(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study = await _build_study(
        client, seed_user, seed_project, seed_instrument_draft, requires_invitation=False
    )
    response = await client.post(
        f"/api/v1/studies/{study['id']}/invitations", json={"count": 1}
    )
    assert response.status_code == 409, response.text


async def test_invitation_issuance_is_rejected_after_campaign_close(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study = await _build_study(
        client, seed_user, seed_project, seed_instrument_draft, requires_invitation=True
    )
    closed = await client.post(f"/api/v1/studies/{study['id']}/close")
    assert closed.status_code == 200, closed.text

    response = await client.post(
        f"/api/v1/studies/{study['id']}/invitations", json={"count": 1}
    )
    assert response.status_code == 409, response.text

    summary = await client.get(f"/api/v1/studies/{study['id']}/invitations")
    assert summary.status_code == 200
    assert summary.json()["total"] == 0


async def test_revoked_invitation_cannot_be_used_and_is_listed(
    client: AsyncClient, seed_user, seed_project, seed_instrument_draft
) -> None:
    study = await _build_study(
        client, seed_user, seed_project, seed_instrument_draft, requires_invitation=True
    )
    issued = await client.post(
        f"/api/v1/studies/{study['id']}/invitations", json={"count": 1}
    )
    assert issued.status_code == 201, issued.text
    token = issued.json()["tokens"][0]
    listing = await client.get(f"/api/v1/studies/{study['id']}/invitations/list")
    assert listing.status_code == 200, listing.text
    invitation_id = listing.json()[0]["id"]

    auth_headers = {"Authorization": f"Bearer {create_access_token(seed_user.id)}"}
    revoked = await client.post(
        f"/api/v1/studies/{study['id']}/invitations/{invitation_id}/revoke",
        params={"reason": "Duplicada"},
        headers=auth_headers,
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "REVOKED"

    again = await client.post(
        f"/api/v1/studies/{study['id']}/invitations/{invitation_id}/revoke",
        params={"reason": "Duplicada"},
        headers=auth_headers,
    )
    assert again.status_code == 200, again.text

    denied = await client.post(
        f"/api/v1/public/studies/{study['public_id']}/response-sessions",
        json={"invitation_token": token},
    )
    assert denied.status_code == 404, denied.text
    assert denied.json()["error_code"] == "PUBLIC_RESOURCE_UNAVAILABLE"

    summary = await client.get(
        f"/api/v1/studies/{study['id']}/invitations",
        params={"include_revoked": "true"},
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["revoked"] == 1
