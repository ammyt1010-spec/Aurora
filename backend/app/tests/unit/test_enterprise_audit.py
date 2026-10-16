"""Authorization, tenant scoping and payload redaction for enterprise audit feed."""
import pytest

from app.core.security import create_access_token
from app.models.audit import AuditLog
from app.models.project import Project
from app.models.user import Organization, OrganizationMembership, User
from app.services.audit_service import AuditService


def bearer(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.session_version)}"}


@pytest.mark.asyncio
async def test_enterprise_audit_scopes_and_redacts_events(client, session):
    admin_a = User(email="audita@aurora.test", username="audita", status="ACTIVE")
    admin_b = User(email="auditb@aurora.test", username="auditb", status="ACTIVE")
    collaborator = User(email="auditviewer@aurora.test", username="auditviewer", status="ACTIVE")
    session.add_all([admin_a, admin_b, collaborator])
    await session.flush()

    org_a = Organization(name="Audit A", status="ACTIVE")
    org_b = Organization(name="Audit B", status="ACTIVE")
    session.add_all([org_a, org_b])
    await session.flush()

    session.add_all([
        OrganizationMembership(organization_id=org_a.id, user_id=admin_a.id, role_code="OWNER", permissions={}),
        OrganizationMembership(organization_id=org_a.id, user_id=collaborator.id, role_code="COLLABORATOR", permissions={}),
        OrganizationMembership(organization_id=org_b.id, user_id=admin_b.id, role_code="ADMIN", permissions={}),
    ])
    project_a = Project(owner_user_id=admin_a.id, organization_id=org_a.id, name="Private A", project_type="CENSO", status="DRAFT")
    project_b = Project(owner_user_id=admin_b.id, organization_id=org_b.id, name="Private B", project_type="CENSO", status="DRAFT")
    session.add_all([project_a, project_b])
    await session.flush()

    audit = AuditService(session)
    # Even if previously logged JSON includes secrets, the API must never expose them.
    await audit.log(action="PROJECT_CREATED", entity_type="project", entity_id=project_a.id,
                    user_id=admin_a.id, organization_id=org_a.id, project_id=project_a.id,
                    after_data={"sensitive_data": "SECRET_NEVER_EXPOSE"})
    await audit.log(action="PROJECT_MEMBER_ADDED", entity_type="project_member", entity_id=collaborator.id,
                    user_id=admin_a.id, project_id=project_a.id)
    await audit.log(action="PROJECT_CREATED", entity_type="project", entity_id=project_b.id,
                    user_id=admin_b.id, organization_id=org_b.id, project_id=project_b.id)
    # Corrupt cross-organization metadata must not disclose another firm's project.
    await audit.log(action="CORRUPT_CROSS_TENANT", entity_type="project", entity_id=project_a.id,
                    user_id=admin_b.id, organization_id=org_b.id, project_id=project_a.id)
    await session.commit()

    path_a = f"/api/v1/organizations/{org_a.id}/audit-events"
    path_b = f"/api/v1/organizations/{org_b.id}/audit-events"

    response = await client.get(path_a, headers=bearer(admin_a))
    assert response.status_code == 200
    events = response.json()["items"]
    assert {e["action"] for e in events} == {"PROJECT_CREATED", "PROJECT_MEMBER_ADDED"}
    assert all("before_data" not in e and "after_data" not in e for e in events)
    assert "SECRET_NEVER_EXPOSE" not in response.text
    assert all(event["project_id"] == project_a.id for event in events)

    response = await client.get(path_b, headers=bearer(admin_b))
    assert response.status_code == 200
    assert [item["action"] for item in response.json()["items"]] == ["PROJECT_CREATED"]

    assert (await client.get(path_a, headers=bearer(admin_b))).status_code == 403
    assert (await client.get(path_a, headers=bearer(collaborator))).status_code == 403
    assert (await client.get(path_a)).status_code == 401


@pytest.mark.asyncio
async def test_enterprise_audit_cursor_and_limit(client, session):
    user = User(email="auditorcursor@aurora.test", username="auditorcursor", status="ACTIVE")
    session.add(user)
    await session.flush()
    org = Organization(name="Audit Cursor", status="ACTIVE")
    session.add(org)
    await session.flush()
    session.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role_code="ADMIN", permissions={}))
    for n in range(4):
        await AuditService(session).log(
            action=f"CURSOR_{n}", entity_type="organization", entity_id=org.id,
            user_id=user.id, organization_id=org.id,
        )
    await session.commit()
    path = f"/api/v1/organizations/{org.id}/audit-events"
    first = await client.get(path + "?limit=2", headers=bearer(user))
    assert first.status_code == 200
    assert [e["action"] for e in first.json()["items"]] == ["CURSOR_3", "CURSOR_2"]
    assert first.json()["next_before_id"] is not None
    second = await client.get(path + f"?limit=2&before_id={first.json()['next_before_id']}", headers=bearer(user))
    assert second.status_code == 200
    assert [e["action"] for e in second.json()["items"]] == ["CURSOR_1", "CURSOR_0"]
    assert second.json()["next_before_id"] is None
    assert (await client.get(path + "?limit=101", headers=bearer(user))).status_code == 422
