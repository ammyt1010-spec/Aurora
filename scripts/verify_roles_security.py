"""Fail-closed security checks against two explicitly provisioned local QA tenants.

Requires AURORA_QA_ISOLATED=1, AURORA_QA_API_URL, and for each TENANT_A/B:
AURORA_QA_TENANT_A_EMAIL, _PASSWORD, _PROJECT_ID, _STUDY_ID (likewise B).
The projects and studies must already exist in distinct organizations. This
script never seeds, rotates credentials, or treats missing IDs as isolation proof.
It checks login, CSRF, cross-tenant access and logout; not demo quotas.
"""
import json
import secrets
from pathlib import Path

import httpx

from qa_test_support import credentials, isolated_url, required_env, require_check


def test_security():
    base_url = isolated_url("AURORA_QA_API_URL")
    tenants = [
        {"auth": credentials(f"AURORA_QA_TENANT_{label}"),
         "project": int(required_env(f"AURORA_QA_TENANT_{label}_PROJECT_ID")),
         "study": int(required_env(f"AURORA_QA_TENANT_{label}_STUDY_ID"))}
        for label in ("A", "B")
    ]
    output = Path(required_env("AURORA_QA_OUTPUT_DIR")) / "security_results.json"
    results = {}
    clients = [httpx.Client(base_url=base_url, timeout=10) for _ in tenants]
    try:
        for index, (client, tenant) in enumerate(zip(clients, tenants)):
            response = client.post("/auth/login", json=tenant["auth"])
            require_check(results, f"tenant_{index}_login", response.status_code == 200)
            tenant["headers"] = {"Authorization": f"Bearer {response.json()['access_token']}"}
            # Use bearer-only requests except for the explicit CSRF test below.
            tenant["session"] = client.cookies.get("aurora_session")
            tenant["csrf"] = client.cookies.get("aurora_csrf")
            client.cookies.clear()
            project = client.get(f"/projects/{tenant['project']}", headers=tenant["headers"])
            require_check(results, f"tenant_{index}_project_exists", project.status_code == 200)
            tenant["organization"] = project.json()["organization_id"]
            study = client.get(f"/studies/{tenant['study']}", headers=tenant["headers"])
            require_check(results, f"tenant_{index}_study_exists", study.status_code == 200)
            require_check(results, f"tenant_{index}_study_belongs_to_project",
                          study.json()["project_id"] == tenant["project"])
        require_check(results, "two_distinct_existing_tenants",
                      all(t["organization"] is not None for t in tenants)
                      and tenants[0]["organization"] != tenants[1]["organization"]
                      and tenants[0]["project"] != tenants[1]["project"])

        bad = clients[0].post("/auth/login", json={
            "email": f"nonexistent-{secrets.token_hex(12)}@invalid.example",
            "password": secrets.token_urlsafe(32),
        })
        require_check(results, "wrong_credentials_rejected", bad.status_code == 401)

        for index, (client, tenant) in enumerate(zip(clients, tenants)):
            other = tenants[1 - index]
            for suffix in ("", "/telemetry"):
                response = client.get(f"/projects/{other['project']}{suffix}", headers=tenant["headers"])
                require_check(results, f"tenant_{index}_cross_project{suffix}_blocked",
                              response.status_code in (403, 404))
            response = client.post(f"/studies/{other['study']}/reports/preview",
                                   json={"report_mode": "PROVISIONAL"}, headers=tenant["headers"])
            require_check(results, f"tenant_{index}_cross_report_blocked", response.status_code in (403, 404))

        client, tenant = clients[0], tenants[0]
        require_check(results, "session_cookie_issued", bool(tenant["session"]))
        client.cookies.set("aurora_session", tenant["session"])
        # Empty update: a broken CSRF guard must not modify fixture data.
        response = client.patch(f"/projects/{tenant['project']}", json={})
        require_check(results, "csrf_protection_enforced", response.status_code == 403)
        client.cookies.clear()
        response = client.post("/auth/logout", headers=tenant["headers"])
        require_check(results, "logout_success", response.status_code in (200, 204))
        response = client.get("/auth/me", headers=tenant["headers"])
        require_check(results, "token_revocation_effective", response.status_code == 401)
    finally:
        for client in clients:
            client.close()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("All configured security checks passed.")
    return results


if __name__ == "__main__":
    test_security()
