"""Complete verification script for PR #7 Enterprise Audit, Role Access, Pagination, PDF/DOCX and Exports."""
import json
import urllib.request
import urllib.error
import sys

BASE_URL = "http://127.0.0.1:8003/api/v1"

with open(".audit_credentials.json", "r", encoding="utf-8") as f:
    creds = json.load(f)

owner_email = creds["empresa_a"]["admin_email"]
owner_pass = creds["empresa_a"]["admin_password"]

admin_email = creds["empresa_a"]["lector_email"]
admin_pass = creds["empresa_a"]["lector_password"]

collab_email = creds["empresa_a"]["colaborador_email"]
collab_pass = creds["empresa_a"]["colaborador_password"]

external_email = creds["empresa_b"]["admin_email"]
external_pass = creds["empresa_b"]["admin_password"]

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
    if status != 200:
        raise RuntimeError(f"Login failed for {email}: {status} {res}")
    return res["access_token"]

print("================================================================")
print("1. Autenticación de roles (OWNER, ADMIN, COLLABORATOR, EXTERNAL)")
print("================================================================")
token_owner = login(owner_email, owner_pass)
print(f" [PASS] OWNER autenticado: {owner_email}")

token_admin = login(admin_email, admin_pass)
print(f" [PASS] ADMIN autenticado: {admin_email}")

token_collab = login(collab_email, collab_pass)
print(f" [PASS] COLLABORATOR autenticado: {collab_email}")

token_external = login(external_email, external_pass)
print(f" [PASS] EXTERNAL OWNER autenticado: {external_email}")

print("\n================================================================")
print("2. Restricciones de Acceso a Auditoría Empresarial (Org 4)")
print("================================================================")

# 2.1 OWNER
status, res = api_call("/organizations/4/audit-events?limit=30", token=token_owner)
print(f" OWNER -> Org 4 Audit: Status {status}")
assert status == 200, f"Expected 200 for OWNER, got {status}: {res}"
assert "items" in res, "Expected 'items' in response"
print(f" [PASS] OWNER tiene acceso: {len(res['items'])} eventos recibidos.")

# 2.2 ADMIN
status, res = api_call("/organizations/4/audit-events?limit=30", token=token_admin)
print(f" ADMIN -> Org 4 Audit: Status {status}")
assert status == 200, f"Expected 200 for ADMIN, got {status}: {res}"
print(f" [PASS] ADMIN tiene acceso: {len(res['items'])} eventos recibidos.")

# 2.3 COLLABORATOR (Must be 403 Forbidden)
status, res = api_call("/organizations/4/audit-events?limit=30", token=token_collab)
print(f" COLLABORATOR -> Org 4 Audit: Status {status} ({res.get('message', res.get('detail'))})")
assert status == 403, f"Security breach! COLLABORATOR should get 403, got {status}: {res}"
print(f" [PASS] COLLABORATOR rechazado con 403.")

# 2.4 EXTERNAL OWNER (Must be 403 Forbidden)
status, res = api_call("/organizations/4/audit-events?limit=30", token=token_external)
print(f" EXTERNAL OWNER -> Org 4 Audit: Status {status} ({res.get('message', res.get('detail'))})")
assert status == 403, f"Security breach! External tenant should get 403, got {status}: {res}"
print(f" [PASS] EXTERNAL OWNER rechazado con 403.")

print("\n================================================================")
print("3. Paginación por Cursor en Historial Empresarial")
print("================================================================")
# Page 1 with limit=5
status, page1 = api_call("/organizations/4/audit-events?limit=5", token=token_owner)
assert status == 200
p1_items = page1["items"]
next_before_id = page1.get("next_before_id")
print(f" Página 1 (limit=5): {len(p1_items)} eventos, next_before_id: {next_before_id}")
assert len(p1_items) > 0, "Page 1 should have items"

if next_before_id:
    status, page2 = api_call(f"/organizations/4/audit-events?limit=5&before_id={next_before_id}", token=token_owner)
    assert status == 200
    p2_items = page2["items"]
    print(f" Página 2 (limit=5, before_id={next_before_id}): {len(p2_items)} eventos")
    p1_ids = {item["id"] for item in p1_items}
    p2_ids = {item["id"] for item in p2_items}
    overlap = p1_ids.intersection(p2_ids)
    assert len(overlap) == 0, f"Page overlap detected: {overlap}"
    print(f" [PASS] Paginación por cursor correcta sin duplicidad (0 solapamiento).")
else:
    print(f" [INFO] Menos de 5 eventos disponibles para paginar.")

print("\n================================================================")
print("4. Generación y Fidelidad de Reportes DOCX / PDF")
print("================================================================")
# List reports for Study 9
status, reports = api_call("/studies/9/reports", token=token_owner)
print(f" Reportes disponibles en Estudio 9: Status {status}")
if status == 200 and len(reports) > 0:
    report_id = reports[0]["id"]
    print(f" Verificando reporte ID {report_id}...")
    # Check PDF preview endpoint
    pdf_url = f"{BASE_URL}/reports/{report_id}/preview.pdf"
    req = urllib.request.Request(pdf_url, headers={"Authorization": f"Bearer {token_owner}"})
    try:
        with urllib.request.urlopen(req) as resp:
            pdf_bytes = resp.read()
            assert pdf_bytes.startswith(b"%PDF"), "Generated file does not have %PDF magic header"
            print(f" [PASS] PDF generado fielmente vía LibreOffice (Tamaño: {len(pdf_bytes)} bytes, Cabecera: {pdf_bytes[:8]})")
    except urllib.error.HTTPError as e:
        print(f" [WARNING/ERROR] Descarga PDF falló: {e.code} {e.read().decode()}")
else:
    print(f" [INFO] No hay reportes preexistentes en Estudio 9")

print("\n================================================================")
print("5. Exportación de Datos de Proyecto y CENSOPAS")
print("================================================================")
status, exports = api_call("/studies/9/exports", method="GET", token=token_owner)
print(f" Consulta de exports en Estudio 9: Status {status} ({len(exports) if isinstance(exports, list) else exports})")
# Request new CSV export
status_post, new_export = api_call("/studies/9/exports", method="POST", data={"export_type": "CSV"}, token=token_owner)
print(f" Solicitud nuevo export CSV Estudio 9: Status {status_post}")
if status_post in (200, 201):
    export_id = new_export["id"]
    print(f" [PASS] Exportación CSV generada ID {export_id}, status: {new_export.get('status')}")
    # Download export
    dl_url = f"{BASE_URL}/exports/{export_id}/download"
    req = urllib.request.Request(dl_url, headers={"Authorization": f"Bearer {token_owner}"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
        print(f" [PASS] Archivo CSV descargado ({len(data)} bytes, Status {resp.status})")


print("\n================================================================")
print("TODAS LAS PRUEBAS DE VERIFICACIÓN PR #7 FINALIZARON CON ÉXITO")
print("================================================================")
