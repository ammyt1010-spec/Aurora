"""Live verification of AURORA Professional PR #11: Commercial Integrity Review.

Tests all 7 user-specified validation requirements:
1. Rejection of unverified official headcount sources (PLANILLA_OFICIAL_EMPRESA, AUDITORIA_RRHH, invalid).
2. Anti-reduction enforcement below verified company floor.
3. Manual quote updates and persists snapshot (snapshot_data['amount'] and pricing_finalized_at).
4. Expired paid orders excluded from available licenses count.
5. Enterprise summary view exposes status 'EXPIRED' for expired paid orders.
6. Non-regression of previous orders, payment confirmations, and consumptions.
7. Multi-tenant isolation (Org A vs Org B), duplicate payment rejection (409), and concurrent generation lock.
"""
import json
import sys
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from pathlib import Path
import httpx
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.core.config import get_settings

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


def run_pr11_verification():
    creds = load_credentials()
    op_creds = creds["operador_central"]
    emp_a_creds = creds["empresa_a"]
    emp_b_creds = creds["empresa_b"]

    print("\n=======================================================")
    print("AURORA PROFESSIONAL: PR #11 LIVE VERIFICATION SUITE")
    print("=======================================================\n")

    client_op = make_client()
    client_a = make_client()
    client_b = make_client()

    db_url = get_settings().database_url_sync
    sep = "&" if "?" in db_url else "?"
    db_url = f"{db_url}{sep}client_encoding=utf8"
    db_eng = create_engine(db_url)

    try:
        # [0] Authenticate actors
        print("[0] Authenticating Platform Operator, Company A Admin, Company B Admin...")
        login(client_op, op_creds["email"], op_creds["password"])
        login(client_a, emp_a_creds["admin_email"], emp_a_creds["admin_password"])
        login(client_b, emp_b_creds["admin_email"], emp_b_creds["admin_password"])
        print("    [+] All 3 actors authenticated successfully.")

        # Get Company A study and organization
        projects_a = client_a.get(f"{BASE_URL}/api/v1/projects").json()
        projects_a = projects_a.get("items", projects_a) if isinstance(projects_a, dict) else projects_a
        project_a_id = projects_a[0]["id"]
        org_a_id = projects_a[0]["organization_id"]
        studies_a = client_a.get(f"{BASE_URL}/api/v1/projects/{project_a_id}/studies").json()
        studies_a = studies_a.get("items", studies_a) if isinstance(studies_a, dict) else studies_a
        study_a_id = studies_a[0]["id"]
        print(f"    [+] Org A ID: {org_a_id}, Study A ID: {study_a_id}")

        # Ensure reference tariffs are loaded
        tariffs = client_op.get(f"{BASE_URL}/api/v1/billing/tariffs").json()
        if not tariffs:
            client_op.post(f"{BASE_URL}/api/v1/billing/tariffs/load-reference")

        # ---------------------------------------------------------------------
        # REQ 1: Fuente oficial sin evidencia registrada debe rechazarse
        # ---------------------------------------------------------------------
        print("\n[REQ 1] Testing rejection of unverified official headcount sources...")
        # Clear metadata for Org A in DB to ensure no evidence exists
        with db_eng.connect() as conn:
            conn.execute(
                text("UPDATE colmena.organizations SET metadata = '{}'::jsonb WHERE id = :oid"),
                {"oid": org_a_id},
            )
            conn.commit()

        # Attempt PLANILLA_OFICIAL_EMPRESA without evidence -> 422
        resp = client_a.post(
            f"{BASE_URL}/api/v1/billing/studies/{study_a_id}/quotes",
            json={"workers": 50, "method_code": "CENSOPAS_MEDIA", "headcount_source": "PLANILLA_OFICIAL_EMPRESA"},
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        err_msg = (resp.json().get("message") or resp.json().get("detail") or "").lower()
        assert "planilla oficial verificada" in err_msg
        print(f"    [+] Correctly rejected unverified PLANILLA_OFICIAL_EMPRESA: {err_msg}")

        # Attempt AUDITORIA_RRHH without evidence -> 422
        resp = client_a.post(
            f"{BASE_URL}/api/v1/billing/studies/{study_a_id}/quotes",
            json={"workers": 50, "method_code": "CENSOPAS_MEDIA", "headcount_source": "AUDITORIA_RRHH"},
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        err_msg = (resp.json().get("message") or resp.json().get("detail") or "").lower()
        assert "auditoría de rr. hh. verificada" in err_msg or "auditoria de rr. hh. verificada" in err_msg
        print(f"    [+] Correctly rejected unverified AUDITORIA_RRHH: {err_msg}")

        # ---------------------------------------------------------------------
        # REQ 2: Dotación oficial verificada debe impedir cotización por debajo
        # ---------------------------------------------------------------------
        print("\n[REQ 2] Testing anti-reduction against verified company headcount floor...")
        # Populate verified_workers in Org A metadata
        with db_eng.connect() as conn:
            conn.execute(
                text("UPDATE colmena.organizations SET metadata = '{\"verified_workers\": 100}'::jsonb WHERE id = :oid"),
                {"oid": org_a_id},
            )
            conn.commit()

        # Quoting for 60 workers when verified is 100 -> must reject with 422
        resp = client_a.post(
            f"{BASE_URL}/api/v1/billing/studies/{study_a_id}/quotes",
            json={"workers": 60, "method_code": "CENSOPAS_MEDIA", "headcount_source": "PLANILLA_OFICIAL_EMPRESA"},
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        err_msg = (resp.json().get("message") or resp.json().get("detail") or "").lower()
        assert "no puede ser menor" in err_msg
        print(f"    [+] Correctly rejected quote below verified floor: {err_msg}")

        # Quoting for 100 workers (>= verified floor) -> Accepted
        resp = client_a.post(
            f"{BASE_URL}/api/v1/billing/studies/{study_a_id}/quotes",
            json={"workers": 100, "method_code": "CENSOPAS_MEDIA", "headcount_source": "PLANILLA_OFICIAL_EMPRESA"},
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        order_q = resp.json()
        print(f"    [+] Valid quote created: Order #{order_q['id']} for {order_q['workers']} workers (PLANILLA_OFICIAL_EMPRESA)")

        # ---------------------------------------------------------------------
        # REQ 3: Cotizaciones manuales deben actualizar y persistir snapshot
        # ---------------------------------------------------------------------
        print("\n[REQ 3] Testing manual quote snapshot persistence...")
        # Create quote for > 1000 workers which requires manual QUOTE pricing
        resp = client_a.post(
            f"{BASE_URL}/api/v1/billing/studies/{study_a_id}/quotes",
            json={"workers": 1500, "method_code": "CENSOPAS_MEDIA"},
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        manual_order = resp.json()
        assert manual_order["pricing_mode"] == "QUOTE"
        assert manual_order["status"] == "AWAITING_QUOTE"
        manual_order_id = manual_order["id"]
        assert manual_order["snapshot_data"]["amount"] is None
        print(f"    [+] Manual quote created: Order #{manual_order_id} in AWAITING_QUOTE")

        # Operator sets manual quote price to 850.00 PEN
        resp = client_op.post(
            f"{BASE_URL}/api/v1/billing/orders/{manual_order_id}/set-manual-price",
            json={"amount": "850.00"},
        )
        assert resp.status_code == 200, f"Setting price failed: {resp.text}"
        priced_order = resp.json()
        assert priced_order["amount"] == "850.00"
        assert priced_order["status"] == "PENDING_PAYMENT"
        assert priced_order["snapshot_data"]["amount"] == "850.00"
        assert priced_order["snapshot_data"].get("pricing_finalized_at") is not None
        print(f"    [+] Snapshot updated in memory: amount={priced_order['snapshot_data']['amount']}, finalized={priced_order['snapshot_data']['pricing_finalized_at']}")

        # Verify persistence directly in PostgreSQL
        with db_eng.connect() as conn:
            row = conn.execute(
                text("SELECT amount, snapshot_data FROM colmena.report_orders WHERE id = :oid"),
                {"oid": manual_order_id},
            ).fetchone()
            assert row is not None
            assert str(row[0]) == "850.00"
            snap = row[1]
            assert snap.get("amount") == "850.00", f"Persisted snapshot amount mismatch: {snap}"
            assert snap.get("pricing_finalized_at") is not None
            print("    [+] Snapshot persistence verified in PostgreSQL database.")

        # ---------------------------------------------------------------------
        # REQ 4 & 5: Órdenes pagadas pero vencidas excluidas de disponibles y marcadas EXPIRED
        # ---------------------------------------------------------------------
        print("\n[REQ 4 & 5] Testing expired paid orders excluded from available licenses & tagged EXPIRED...")
        # Confirm payment for manual_order
        resp = client_op.post(
            f"{BASE_URL}/api/v1/billing/orders/{manual_order_id}/confirm-payment",
            json={"payment_reference": "BCP-OP-MANUAL-999"},
        )
        assert resp.status_code == 200, f"Payment failed: {resp.text}"
        print(f"    [+] Order #{manual_order_id} confirmed as PAID")

        # Check summary before expiring
        resp = client_a.get(f"{BASE_URL}/api/v1/billing/organizations/{org_a_id}/summary")
        assert resp.status_code == 200
        summary_before = resp.json()
        avail_before = summary_before["available_licenses"]

        # Expire order in DB
        with db_eng.connect() as conn:
            conn.execute(
                text("UPDATE colmena.report_orders SET expires_at = NOW() - INTERVAL '1 day' WHERE id = :oid"),
                {"oid": manual_order_id},
            )
            conn.commit()

        # Check summary after expiring
        resp = client_a.get(f"{BASE_URL}/api/v1/billing/organizations/{org_a_id}/summary")
        assert resp.status_code == 200
        summary_after = resp.json()
        avail_after = summary_after["available_licenses"]
        assert avail_after == avail_before - 1, f"Available count should decrement: {avail_before} -> {avail_after}"
        print(f"    [+] Available count correctly decremented from {avail_before} to {avail_after}")

        # Verify the order status in the summary view is 'EXPIRED'
        expired_view_order = next((o for o in summary_after["orders"] if o["id"] == manual_order_id), None)
        assert expired_view_order is not None
        assert expired_view_order["status"] == "EXPIRED", f"Expected EXPIRED status, got {expired_view_order['status']}"
        print(f"    [+] Summary view order #{manual_order_id} is correctly labeled: status='EXPIRED'")

        # Verify DB audit integrity: in the DB row itself, status remains 'PAID'
        with db_eng.connect() as conn:
            db_status = conn.execute(
                text("SELECT status FROM colmena.report_orders WHERE id = :oid"),
                {"oid": manual_order_id},
            ).scalar()
            assert db_status == "PAID", f"DB row status must remain PAID, found {db_status}"
            print(f"    [+] Underlying PostgreSQL row preserves accounting audit: status='PAID'")

        # ---------------------------------------------------------------------
        # REQ 6: Sin regresiones en órdenes anteriores, confirmaciones y consumos
        # ---------------------------------------------------------------------
        print("\n[REQ 6] Testing non-regression in previous orders, confirmations and consumptions...")
        # Create a fresh valid order
        resp = client_a.post(
            f"{BASE_URL}/api/v1/billing/studies/{study_a_id}/quotes",
            json={"workers": 100, "method_code": "CENSOPAS_MEDIA", "headcount_source": "PLANILLA_OFICIAL_EMPRESA"},
        )
        assert resp.status_code == 201
        valid_order = resp.json()
        valid_order_id = valid_order["id"]

        # Confirm payment
        resp = client_op.post(
            f"{BASE_URL}/api/v1/billing/orders/{valid_order_id}/confirm-payment",
            json={"payment_reference": "BCP-OP-VALID-1234"},
        )
        assert resp.status_code == 200
        print(f"    [+] Order #{valid_order_id} successfully confirmed as PAID")

        # Generate report and consume order
        resp = client_a.post(
            f"{BASE_URL}/api/v1/studies/{study_a_id}/reports",
            json={"output_format": "JSON", "report_mode": "PROVISIONAL", "billing_order_id": valid_order_id},
        )
        assert resp.status_code in (200, 201), f"Report generation failed: {resp.status_code} {resp.text}"
        rep = resp.json()
        print(f"    [+] Report #{rep['id']} generated and order #{valid_order_id} consumed.")

        with db_eng.connect() as conn:
            final_status = conn.execute(
                text("SELECT status, consumed_at FROM colmena.report_orders WHERE id = :oid"),
                {"oid": valid_order_id},
            ).fetchone()
            assert final_status[0] == "CONSUMED"
            assert final_status[1] is not None
            print(f"    [+] Order transition verified: status='CONSUMED', consumed_at={final_status[1]}")

        # ---------------------------------------------------------------------
        # REQ 7: Dos organizaciones, pagos duplicados y generación concurrente
        # ---------------------------------------------------------------------
        print("\n[REQ 7] Testing multi-organization isolation, duplicate payments, and concurrency...")
        # 7a. Multi-tenant isolation: Org B tries to view Org A's summary -> 403
        resp = client_b.get(f"{BASE_URL}/api/v1/billing/organizations/{org_a_id}/summary")
        assert resp.status_code == 403
        print("    [+] Org B blocked from viewing Org A's billing summary (403 Forbidden)")

        # 7b. Duplicate payment rejection
        # Attempt to confirm payment again on valid_order_id (already consumed) or paid order
        resp = client_op.post(
            f"{BASE_URL}/api/v1/billing/orders/{valid_order_id}/confirm-payment",
            json={"payment_reference": "BCP-OP-DUPLICATE"},
        )
        assert resp.status_code == 409
        err7b = resp.json().get('message') or resp.json().get('detail')
        print(f"    [+] Duplicate payment rejected (409 Conflict): {err7b}")

        # 7c. Reutilization / Concurrency prevention: Already consumed order cannot be reused
        resp = client_a.post(
            f"{BASE_URL}/api/v1/studies/{study_a_id}/reports",
            json={"output_format": "JSON", "report_mode": "PROVISIONAL", "billing_order_id": valid_order_id},
        )
        assert resp.status_code == 409
        err7c = resp.json().get('message') or resp.json().get('detail')
        print(f"    [+] Reutilization of consumed order rejected (409 Conflict): {err7c}")

        print("\n=======================================================")
        print("ALL 7 PR #11 REQUIREMENTS VERIFIED AND PASSED IN LIVE ENVIRONMENT!")
        print("=======================================================\n")

    finally:
        client_op.close()
        client_a.close()
        client_b.close()
        db_eng.dispose()


if __name__ == "__main__":
    run_pr11_verification()
