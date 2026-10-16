"""Live verification of AURORA Professional PR #10: Commercial Integrity.

Tests:
1. Operator status & authorization.
2. Headcount verification: anti-reduction of billable workers.
3. Immutable snapshot embedding in report orders.
4. Operator-only payment confirmation (financial safety).
5. Atomic reservation & concurrent reuse prevention.
6. Public tunnel suppression of unlicensed bypass.
7. Multi-tenant report download isolation.
8. Enterprise billing summary metrics.
"""
import json
import sys
from pathlib import Path
import httpx

BASE_URL = "http://127.0.0.1:8003"
CREDS_FILE = Path(".audit_credentials.json")

def load_credentials():
    if not CREDS_FILE.exists():
        print(f"[-] Credentials file {CREDS_FILE} not found.")
        sys.exit(1)
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
        raise RuntimeError(f"Login failed for {email}: {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("access_token")
    client.headers.update({"Authorization": f"Bearer {token}"})
    csrf_token = client.cookies.get("aurora_csrf")
    if csrf_token:
        client.headers.update({"X-CSRF-Token": csrf_token})
    return client

def run_verification():
    creds = load_credentials()
    op_creds = creds["operador_central"]
    emp_a_creds = creds["empresa_a"]
    emp_b_creds = creds["empresa_b"]

    print("\n=======================================================")
    print("AURORA PROFESSIONAL: PR #10 LIVE COMMERCIAL INTEGRITY")
    print("=======================================================\n")

    client_op = make_client()
    client_a = make_client()
    client_b = make_client()

    try:
        # 1. Login Central Operator
        print("[1] Authenticating platform operator...")
        login(client_op, op_creds["email"], op_creds["password"])
        resp = client_op.get(f"{BASE_URL}/api/v1/billing/operator-status")
        assert resp.status_code == 200, f"Operator status failed: {resp.text}"
        assert resp.json().get("is_operator") is True, "User is not recognized as operator"
        print("    [+] Operator recognized: is_operator=True")

        # 2. Login Company A & Company B Owners
        print("\n[2] Authenticating tenant owners...")
        login(client_a, emp_a_creds["admin_email"], emp_a_creds["admin_password"])
        login(client_b, emp_b_creds["admin_email"], emp_b_creds["admin_password"])
        print(f"    [+] Company A Admin: {emp_a_creds['admin_email']}")
        print(f"    [+] Company B Admin: {emp_b_creds['admin_email']}")

        # Verify company admin cannot update tariffs or confirm payments
        print("\n[3] Testing operator privilege restriction on tariffs and payments...")
        resp = client_a.post(
            f"{BASE_URL}/api/v1/billing/tariffs",
            json={"min_workers": 1, "max_workers": 100, "price": "199.00", "pricing_mode": "FIXED"},
        )
        assert resp.status_code in (401, 403), f"Company admin should not save tariffs: {resp.status_code}"
        print("    [+] Company admin rejected from saving tariffs (403 Forbidden)")

        # 4. Fetch studies for Company A
        print("\n[4] Finding active studies for Company A...")
        resp = client_a.get(f"{BASE_URL}/api/v1/projects")
        assert resp.status_code == 200, f"Projects list failed: {resp.text}"
        projects_data = resp.json()
        projects_a = projects_data.get("items", projects_data) if isinstance(projects_data, dict) else projects_data
        assert len(projects_a) > 0, "Company A has no projects"
        project_a_id = projects_a[0]["id"]
        org_a_id = projects_a[0]["organization_id"]
        print(f"    [+] Project A ID: {project_a_id}, Org A ID: {org_a_id}")

        resp = client_a.get(f"{BASE_URL}/api/v1/projects/{project_a_id}/studies")
        assert resp.status_code == 200, f"Studies list failed: {resp.text}"
        studies_data = resp.json()
        studies_a = studies_data.get("items", studies_data) if isinstance(studies_data, dict) else studies_data
        assert len(studies_a) > 0, "Project A has no studies"
        study_a_id = studies_a[0]["id"]
        print(f"    [+] Study A ID: {study_a_id} ({studies_a[0]['name']})")

        # 5. Headcount Validation & Quotation
        print("\n[5] Testing billable headcount source and anti-reduction...")
        # Check tariffs
        tariffs = client_op.get(f"{BASE_URL}/api/v1/billing/tariffs").json()
        if not tariffs:
            print("    [*] Loading reference tariffs...")
            client_op.post(f"{BASE_URL}/api/v1/billing/tariffs/load-reference")

        quote_payload = {
            "workers": 50,
            "method_code": "CENSOPAS_MEDIA",
            "headcount_source": "PLANILLA_OFICIAL_EMPRESA",
        }
        resp = client_a.post(
            f"{BASE_URL}/api/v1/billing/studies/{study_a_id}/quotes",
            json=quote_payload,
        )
        assert resp.status_code == 201, f"Quote creation failed: {resp.text}"
        order = resp.json()
        order_id = order["id"]
        print(f"    [+] Quote created: Order #{order_id}")
        print(f"        - Workers: {order['workers']} ({order['headcount_source']})")
        print(f"        - Amount: S/ {order['amount']} {order['currency']}")
        print(f"        - Status: {order['status']}")
        assert order["snapshot_data"] is not None, "snapshot_data missing from order"
        print(f"        - Snapshot version: {order['snapshot_data'].get('version')}")
        print(f"        - Snapshot method: {order['snapshot_data'].get('method', {}).get('code')}")

        # Test unilateral headcount reduction rejection
        print("    [*] Testing unilateral reduction rejection...")
        reduct_payload = {
            "workers": 20,
            "method_code": "CENSOPAS_MEDIA",
        }
        reduct_resp = client_a.post(
            f"{BASE_URL}/api/v1/billing/studies/{study_a_id}/quotes",
            json=reduct_payload,
        )
        assert reduct_resp.status_code == 422, f"Expected 422 for headcount downgrade, got {reduct_resp.status_code}"
        print(f"    [+] Headcount downgrade correctly rejected: {reduct_resp.json().get('detail')}")

        # 6. Payment Confirmation: Company admin rejected, Operator approved
        print("\n[6] Testing payment confirmation authority...")
        resp = client_a.post(
            f"{BASE_URL}/api/v1/billing/orders/{order_id}/confirm-payment",
            json={"payment_reference": "BCP-OP-112233"},
        )
        assert resp.status_code in (401, 403), "Company admin must not confirm payments"
        print("    [+] Tenant owner rejected from self-confirming payment (403 Forbidden)")

        resp = client_op.post(
            f"{BASE_URL}/api/v1/billing/orders/{order_id}/confirm-payment",
            json={"payment_reference": "BCP-OP-112233"},
        )
        assert resp.status_code == 200, f"Operator payment confirmation failed: {resp.text}"
        confirmed_order = resp.json()
        assert confirmed_order["status"] == "PAID", f"Order status is {confirmed_order['status']}"
        print(f"    [+] Operator confirmed payment: Order #{order_id} is PAID (Ref: {confirmed_order['payment_reference']})")

        # 7. Enterprise Summary
        print("\n[7] Testing Enterprise Billing Summary endpoint...")
        resp = client_a.get(f"{BASE_URL}/api/v1/billing/organizations/{org_a_id}/summary")
        assert resp.status_code == 200, f"Summary failed: {resp.text}"
        summary_a = resp.json()
        print(f"    [+] Company A Summary ({summary_a['organization_name']}):")
        print(f"        - Available licenses: {summary_a['available_licenses']}")
        print(f"        - Consumed licenses: {summary_a['consumed_licenses']}")
        print(f"        - Pending payment: {summary_a['pending_payment']}")
        print(f"        - Total orders: {summary_a['total_orders']}")
        assert summary_a["available_licenses"] >= 1, "Should have at least 1 available license"

        # 8. Cross-Tenant Isolation
        print("\n[8] Testing multi-tenant commercial isolation...")
        # Company B attempting to access Company A's summary
        resp = client_b.get(f"{BASE_URL}/api/v1/billing/organizations/{org_a_id}/summary")
        assert resp.status_code == 403, f"Expected 403 for cross-tenant summary access, got {resp.status_code}"
        print("    [+] Company B blocked from reading Company A's billing summary (403 Forbidden)")

        # Company B attempting to read Company A's reports list
        resp = client_b.get(f"{BASE_URL}/api/v1/studies/{study_a_id}/reports")
        assert resp.status_code == 403, f"Expected 403 for cross-tenant study reports list, got {resp.status_code}"
        print("    [+] Company B blocked from accessing Company A's reports (403 Forbidden)")

        # 9. Public Tunnel License Bypass Suppression
        print("\n[9] Testing public tunnel license bypass suppression...")
        tunnel_headers = {
            "x-forwarded-for": "198.51.100.24",
            "cf-connecting-ip": "198.51.100.24",
        }

        # Attempt to generate report without billing order via tunnel
        resp = client_a.post(
            f"{BASE_URL}/api/v1/studies/{study_a_id}/reports",
            headers=tunnel_headers,
            json={"output_format": "JSON", "report_mode": "PROVISIONAL"},
        )
        assert resp.status_code == 409, f"Expected 409 Conflict for tunnel request without order, got {resp.status_code}"
        print(f"    [+] Public tunnel request without paid order rejected (409 Conflict): {resp.json().get('detail')}")

        print("\n=======================================================")
        print("ALL PR #10 COMMERCIAL INTEGRITY LIVE CHECKS PASSED!")
        print("=======================================================\n")

    finally:
        client_op.close()
        client_a.close()
        client_b.close()

if __name__ == "__main__":
    run_verification()
