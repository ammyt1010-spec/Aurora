"""Script to verify live global logout (PR #4) and multi-tenant isolation against live backend."""
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8003/api/v1"

with open(".audit_credentials.json", "r", encoding="utf-8") as f:
    creds = json.load(f)

email_a = creds["empresa_a"]["admin_email"]
pass_a = creds["empresa_a"]["admin_password"]
proj_a = creds["empresa_a"]["project_id"]

email_b = creds["empresa_b"]["admin_email"]
pass_b = creds["empresa_b"]["admin_password"]
proj_b = creds["empresa_b"]["project_id"]

def api_call(endpoint, method="GET", data=None, token=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
            return resp.status, json.loads(content.decode("utf-8")) if content else {}
    except urllib.error.HTTPError as e:
        err_content = e.read()
        try:
            err_json = json.loads(err_content.decode("utf-8"))
        except Exception:
            err_json = {"raw": err_content.decode("utf-8", errors="ignore")}
        return e.code, err_json

def login(email, password):
    status, res = api_call("/auth/login", method="POST", data={"email": email, "password": password})
    assert status == 200, f"Login failed for {email}: {status} {res}"
    return res["access_token"]

print("--- 1. Login session 1 for Empresa A ---")
token_a1 = login(email_a, pass_a)
s, me = api_call("/auth/me", token=token_a1)
assert s == 200 and me["email"] == email_a, f"Session A1 me failed: {s} {me}"
print(f"Session A1 OK: User {me['email']}, ID {me['id']}")

print("--- 2. Login session 2 for Empresa A ---")
token_a2 = login(email_a, pass_a)
s, me = api_call("/auth/me", token=token_a2)
assert s == 200 and me["email"] == email_a, f"Session A2 me failed: {s} {me}"
print(f"Session A2 OK: User {me['email']}")

print("--- 3. Login session for Empresa B ---")
token_b = login(email_b, pass_b)
s, me = api_call("/auth/me", token=token_b)
assert s == 200 and me["email"] == email_b, f"Session B me failed: {s} {me}"
print(f"Session B OK: User {me['email']}")

print("--- 4. Execute logout-all from Session A1 ---")
status, res = api_call("/auth/logout-all", method="POST", token=token_a1)
assert status in (200, 204), f"Logout-all failed: {status} {res}"
print(f"Logout-all executed successfully (status {status})")

print("--- 5. Verify Session A1 is revoked (must return 401) ---")
s1, r1 = api_call("/auth/me", token=token_a1)
print(f"Session A1 status: {s1} ({r1.get('detail', r1)})")
assert s1 == 401, f"Expected 401 for Session A1, got {s1}"

print("--- 6. Verify Session A2 is also revoked (must return 401) ---")
s2, r2 = api_call("/auth/me", token=token_a2)
print(f"Session A2 status: {s2} ({r2.get('detail', r2)})")
assert s2 == 401, f"Expected 401 for Session A2, got {s2}"

print("--- 7. Verify Empresa B session is completely unaffected (must return 200) ---")
sb, rb = api_call("/auth/me", token=token_b)
print(f"Session B status: {sb} (User: {rb.get('email')})")
assert sb == 200, f"Expected 200 for Session B, got {sb}"

print("--- 8. Verify new login for Empresa A works and gets fresh valid session ---")
token_a_new = login(email_a, pass_a)
s_new, me_new = api_call("/auth/me", token=token_a_new)
print(f"New Session A status: {s_new} (User: {me_new.get('email')})")
assert s_new == 200, f"Expected 200 for New Session A, got {s_new}"

print("--- 9. Verify Multi-Tenant cross-project isolation ---")
# Empresa B attempts to access Empresa A project
s_cross, r_cross = api_call(f"/projects/{proj_a}", token=token_b)
print(f"Cross-project access Empresa B -> Empresa A (Proj {proj_a}): Status {s_cross}")
assert s_cross in (403, 404), f"Security breach! Empresa B accessed Empresa A project: {s_cross} {r_cross}"

# Empresa A attempts to access Empresa B project
s_cross2, r_cross2 = api_call(f"/projects/{proj_b}", token=token_a_new)
print(f"Cross-project access Empresa A -> Empresa B (Proj {proj_b}): Status {s_cross2}")
assert s_cross2 in (403, 404), f"Security breach! Empresa A accessed Empresa B project: {s_cross2} {r_cross2}"

print("ALL LIVE VERIFICATIONS PASSED SUCCESSFULLY!")
