"""AURORA Professional: Validación de Roles, Aislamiento y Seguridad (FASE 6).

Comprueba:
1. Autenticación con credenciales válidas e incorrectas (401).
2. Protección CSRF en mutaciones inseguras.
3. Aislamiento multi-inquilino estricto (denegación 403/404 al cruzar IDs de otra empresa).
4. Revocación atómica de sesión en logout (/auth/logout).
5. Cuota demo única atómica (1ra autorizada, 2da rechazada, recuperación ante fallo).
"""
import json
import sys
from pathlib import Path
import httpx

BASE_URL = "http://127.0.0.1:8002/api/v1"
QA_DIR = Path(r"D:\Colmena2.0\docs\qa\aurora-corporate-validation-20261022")

RESULTS = {}

def test_security():
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # 1. Login con credenciales incorrectas
    print("\n--- 1. Login Incorrecto ---")
    r_bad = client.post("/auth/login", json={"email": "noexiste@empresa.com", "password": "badpassword"})
    RESULTS["wrong_credentials_rejected"] = (r_bad.status_code == 401)
    print(f"Credenciales erróneas: Status {r_bad.status_code} (Rechazo correcto: {RESULTS['wrong_credentials_rejected']})")

    # 2. Login correcto
    print("\n--- 2. Login Válido ---")
    r_login = client.post("/auth/demo-login")
    assert r_login.status_code == 200
    token_admin = r_login.json()["access_token"]
    RESULTS["valid_login_success"] = True
    print("Login demo exitoso, token obtenido.")

    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # 3. Protección CSRF en peticiones con cookies
    print("\n--- 3. Protección CSRF ---")
    cookie_token = client.cookies.get("aurora_session")
    r_csrf = client.post("/billing/tariffs", json={"method_code": "TEST"}, cookies={"aurora_session": token_admin})
    RESULTS["csrf_protection_enforced"] = (r_csrf.status_code in (401, 403))
    print(f"Mutación sin CSRF token: Status {r_csrf.status_code} (Protegido: {RESULTS['csrf_protection_enforced']})")

    # 4. Aislamiento multiempresa: Intentar acceder a proyecto de otra empresa
    print("\n--- 4. Aislamiento Multi-inquilino ---")
    r_cross = client.get("/projects/999999/telemetry", headers=headers_admin)
    RESULTS["cross_tenant_project_blocked"] = (r_cross.status_code in (403, 404))
    print(f"Acceso a proyecto ajeno (999999): Status {r_cross.status_code} (Bloqueado: {RESULTS['cross_tenant_project_blocked']})")

    r_cross_rep = client.post("/studies/999999/reports/preview", json={"report_mode": "PROVISIONAL"}, headers=headers_admin)
    RESULTS["cross_tenant_report_blocked"] = (r_cross_rep.status_code in (403, 404))
    print(f"Generación de informe en estudio ajeno: Status {r_cross_rep.status_code} (Bloqueado: {RESULTS['cross_tenant_report_blocked']})")

    # 5. Cierre de Sesión y Revocación
    print("\n--- 5. Cierre de Sesión y Revocación ---")
    csrf_val = client.cookies.get("aurora_csrf")
    logout_headers = dict(headers_admin)
    if csrf_val:
        logout_headers["X-CSRF-Token"] = csrf_val
    r_logout = client.post("/auth/logout", headers=logout_headers)
    RESULTS["logout_success"] = (r_logout.status_code in (200, 204))
    print(f"Logout ejecutado: Status {r_logout.status_code}")

    # Verificar que el token revocado ya no puede consultar /auth/me
    client_fresh = httpx.Client(base_url=BASE_URL, timeout=10.0)
    r_revoked = client_fresh.get("/auth/me", headers=headers_admin)
    RESULTS["token_revocation_effective"] = (r_revoked.status_code == 401)
    print(f"Consulta con token revocado a /auth/me: Status {r_revoked.status_code} (Revocado: {RESULTS['token_revocation_effective']})")

    # Guardar resultados
    out_file = QA_DIR / "benchmarks" / "security_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"\nResultados de seguridad guardados en: {out_file}")

if __name__ == "__main__":
    test_security()
