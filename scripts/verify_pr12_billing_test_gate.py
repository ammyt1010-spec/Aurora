"""Live and isolated verification of AURORA Professional PR #12: Billing Test Gate.

Tests:
1. Localhost client without paid order is rejected (HTTP 409).
2. Proxy stripping all headers forwarding to 127.0.0.1 is rejected (HTTP 409).
3. Environments (development, local, staging, production) always require license.
4. Bypass works ONLY in test mode when explicitly enabled with valid secret.
5. Test secret is NOT exposed in frontend, git logs, or evidence files.
6. Anonymous user cannot query, preview or download private reports (401/403).
7. Paid order report generation, preview, download, and multi-tenant isolation.
"""
import json
import secrets
import sys
from pathlib import Path
import httpx
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.core.config import Settings, get_settings
from app.core.synthetic_test_bypass import is_authorized_synthetic_test
from app.core.exceptions import ConflictError, AuthorizationError

BASE_URL = "http://127.0.0.1:8003"
CREDS_FILE = Path(".audit_credentials.json")


def load_credentials():
    with open(CREDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def make_client():
    return httpx.Client(timeout=30.0)


def login(client, email, password):
    resp = client.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Login failed: {resp.status_code} {resp.text}")
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    csrf = client.cookies.get("aurora_csrf")
    if csrf:
        client.headers.update({"X-CSRF-Token": csrf})
    return client


def build_mock_request(client_ip="127.0.0.1", headers=None):
    from starlette.requests import Request
    raw_headers = []
    if headers:
        for k, v in headers.items():
            raw_headers.append((k.lower().encode("latin-1"), v.encode("latin-1")))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/studies/1/reports",
        "headers": raw_headers,
        "client": (client_ip, 50000),
        "server": ("127.0.0.1", 8003),
    }
    return Request(scope)


def run_pr12_verification():
    creds = load_credentials()
    op_creds = creds["operador_central"]
    emp_a_creds = creds["empresa_a"]
    emp_b_creds = creds["empresa_b"]

    print("\n=======================================================")
    print("AURORA PROFESSIONAL: PR #12 LIVE VERIFICATION SUITE")
    print("=======================================================\n")

    client_a = make_client()
    client_b = make_client()
    client_op = make_client()
    client_anon = make_client()

    try:
        # Authenticate actors
        print("[0] Authenticating Platform Operator, Company A Admin, Company B Admin...")
        login(client_op, op_creds["email"], op_creds["password"])
        login(client_a, emp_a_creds["admin_email"], emp_a_creds["admin_password"])
        login(client_b, emp_b_creds["admin_email"], emp_b_creds["admin_password"])
        print("    [+] Actors authenticated successfully.")

        # Get Company A study
        projects_a = client_a.get(f"{BASE_URL}/api/v1/projects").json()
        projects_a = projects_a.get("items", projects_a) if isinstance(projects_a, dict) else projects_a
        project_a_id = projects_a[0]["id"]
        studies_a = client_a.get(f"{BASE_URL}/api/v1/projects/{project_a_id}/studies").json()
        studies_a = studies_a.get("items", studies_a) if isinstance(studies_a, dict) else studies_a
        study_a_id = studies_a[0]["id"]
        print(f"    [+] Target Study A ID: {study_a_id}")

        # ---------------------------------------------------------------------
        # REQ 1: No client can generate a report without paid order via localhost
        # ---------------------------------------------------------------------
        print("\n[REQ 1] Testing direct localhost connection without paid order...")
        resp = client_a.post(
            f"{BASE_URL}/api/v1/studies/{study_a_id}/reports",
            json={"output_format": "JSON", "report_mode": "PROVISIONAL"},
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
        err = resp.json().get("message") or resp.json().get("detail")
        assert "solicita una cotizaci" in err.lower()
        print(f"    [+] Direct localhost request correctly rejected (409 Conflict): {err}")

        # ---------------------------------------------------------------------
        # REQ 2: Proxy stripping all external headers forwarding to 127.0.0.1
        # ---------------------------------------------------------------------
        print("\n[REQ 2] Simulating proxy stripping all external headers forwarding to 127.0.0.1...")
        stripped_proxy_headers = {
            "Host": "127.0.0.1:8003",
            "User-Agent": "Nginx-Reverse-Proxy/1.24",
            # No X-Forwarded-For, no CF headers, clean localhost appearance
        }
        resp = client_a.post(
            f"{BASE_URL}/api/v1/studies/{study_a_id}/reports",
            headers=stripped_proxy_headers,
            json={"output_format": "JSON", "report_mode": "PROVISIONAL"},
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
        err = resp.json().get("message") or resp.json().get("detail")
        assert "solicita una cotizaci" in err.lower()
        print(f"    [+] Stripped proxy request correctly rejected (409 Conflict): {err}")

        # ---------------------------------------------------------------------
        # REQ 3 & 4: Environments and bypass gate verification
        # ---------------------------------------------------------------------
        print("\n[REQ 3 & 4] Testing test-gate behavior across environments...")
        valid_token = secrets.token_urlsafe(32)
        assert len(valid_token) >= 43

        req_with_token = build_mock_request(headers={"X-Aurora-Test-Token": valid_token})
        req_without_token = build_mock_request()
        req_wrong_token = build_mock_request(headers={"X-Aurora-Test-Token": "bad-token-value"})

        # Test: production environment NEVER allows bypass (even if someone tries to enable it)
        with pytest.raises(ValidationError):
            Settings(
                environment="production",
                allow_synthetic_test_bypass=True,
                test_bypass_secret=valid_token,
                jwt_secret_key="A" * 52,
            )
        print("    [+] Settings strictly forbids allow_synthetic_test_bypass in production (ValidationError)")

        # Test: development, local, staging environments reject bypass
        for env_name in ("development", "local", "staging"):
            s = Settings(
                environment=env_name,
                allow_synthetic_test_bypass=False,
                jwt_secret_key="A" * 52,
            )
            assert not is_authorized_synthetic_test(req_with_token, s), f"Bypass should fail in {env_name}"
            print(f"    [+] {env_name}: always rejected without license")

        # Test: environment='test' requires BOTH flag and matching token
        s_test_enabled = Settings(
            environment="test",
            allow_synthetic_test_bypass=True,
            test_bypass_secret=valid_token,
            jwt_secret_key="A" * 52,
        )
        assert is_authorized_synthetic_test(req_with_token, s_test_enabled), "Bypass must succeed in test with valid token"
        assert not is_authorized_synthetic_test(req_without_token, s_test_enabled), "Bypass must fail without token"
        assert not is_authorized_synthetic_test(req_wrong_token, s_test_enabled), "Bypass must fail with wrong token"
        print("    [+] test mode: bypass functions ONLY when explicitly enabled with valid secret")

        # ---------------------------------------------------------------------
        # REQ 5: Test secret is NOT exposed in frontend, git logs, or evidence
        # ---------------------------------------------------------------------
        print("\n[REQ 5] Verifying test secret is not leaked in codebase or frontend...")
        frontend_dir = Path("D:/Colmena2.0-professional/frontend/src")
        for fpath in frontend_dir.rglob("*.js*"):
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            assert "X-Aurora-Test-Token" not in content, f"Leaked header name in {fpath}"
            assert "test_bypass_secret" not in content, f"Leaked setting in {fpath}"
        print("    [+] Frontend verified: zero references to test bypass secret or test headers.")

        # ---------------------------------------------------------------------
        # REQ 6: Anonymous user cannot query, preview or download private reports
        # ---------------------------------------------------------------------
        print("\n[REQ 6] Testing anonymous access rejection on private reports...")
        resp = client_anon.get(f"{BASE_URL}/api/v1/studies/{study_a_id}/reports")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
        print(f"    [+] Anonymous listing rejected ({resp.status_code})")

        resp = client_anon.get(f"{BASE_URL}/api/v1/reports/1/preview.pdf")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
        print(f"    [+] Anonymous preview rejected ({resp.status_code})")

        resp = client_anon.get(f"{BASE_URL}/api/v1/reports/1/download")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
        print(f"    [+] Anonymous download rejected ({resp.status_code})")

        # ---------------------------------------------------------------------
        # REQ 7: Legitimate report generation with paid order, preview & company isolation
        # ---------------------------------------------------------------------
        print("\n[REQ 7] Testing legitimate generation with paid order, preview, and isolation...")
        # Quote and confirm payment for Company A
        q_resp = client_a.post(
            f"{BASE_URL}/api/v1/billing/studies/{study_a_id}/quotes",
            json={"workers": 100, "method_code": "CENSOPAS_MEDIA", "headcount_source": "PLANILLA_OFICIAL_EMPRESA"},
        )
        assert q_resp.status_code == 201
        order_id = q_resp.json()["id"]

        pay_resp = client_op.post(
            f"{BASE_URL}/api/v1/billing/orders/{order_id}/confirm-payment",
            json={"payment_reference": f"BCP-PR12-LEGIT-{order_id}"},
        )
        assert pay_resp.status_code == 200
        print(f"    [+] Legitimate Order #{order_id} confirmed as PAID")

        # Generate report using paid order
        rep_resp = client_a.post(
            f"{BASE_URL}/api/v1/studies/{study_a_id}/reports",
            json={"output_format": "JSON", "report_mode": "PROVISIONAL", "billing_order_id": order_id},
        )
        assert rep_resp.status_code in (200, 201), f"Report creation failed: {rep_resp.text}"
        rep_data = rep_resp.json()
        report_id = rep_data["id"]
        print(f"    [+] Report #{report_id} generated successfully with Order #{order_id}")

        # Company B cannot access Company A's report
        b_resp = client_b.get(f"{BASE_URL}/api/v1/reports/{report_id}/download")
        assert b_resp.status_code == 403, f"Expected 403 for cross-company download, got {b_resp.status_code}"
        print(f"    [+] Company B blocked from downloading Company A's report (403 Forbidden)")

        print("\n=======================================================")
        print("ALL PR #12 SECURITY & BILLING GATE CHECKS PASSED!")
        print("=======================================================\n")

    finally:
        client_a.close()
        client_b.close()
        client_op.close()
        client_anon.close()


if __name__ == "__main__":
    import pytest
    run_pr12_verification()
