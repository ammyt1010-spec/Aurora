"""Verification script for PR #8: User & Device Session Management."""
import json
import urllib.request
import urllib.error
import sys

BASE_URL = "http://127.0.0.1:8003/api/v1"

with open(".audit_credentials.json", "r", encoding="utf-8") as f:
    creds = json.load(f)

admin_a_email = creds["empresa_a"]["admin_email"]
admin_a_pass = creds["empresa_a"]["admin_password"]

admin_b_email = creds["empresa_b"]["admin_email"]
admin_b_pass = creds["empresa_b"]["admin_password"]

def api_call(endpoint, method="GET", data=None, token=None, user_agent=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if user_agent:
        headers["User-Agent"] = user_agent
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

def login(email, password, user_agent=None):
    status, res = api_call("/auth/login", method="POST", data={"email": email, "password": password}, user_agent=user_agent)
    if status != 200:
        raise RuntimeError(f"Login failed for {email}: {status} {res}")
    return res["access_token"]

def main():
    print("=================================================================")
    print("AURORA PROFESSIONAL — PR #8 SESSION MANAGEMENT VERIFICATION")
    print("=================================================================")

    # 1. Login session 1 (Desktop Windows)
    ua_desktop = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    token_1 = login(admin_a_email, admin_a_pass, user_agent=ua_desktop)
    print("\n[OK] 1. Sesion 1 iniciada con token JWT.")

    # 2. List sessions
    status, sessions = api_call("/auth/sessions", token=token_1)
    assert status == 200, f"Error listando sesiones: {status} {sessions}"
    print(f"[OK] 2. Listado de sesiones obtenido: {len(sessions)} sesiones activas.")
    current_session = next((s for s in sessions if s["is_current"]), None)
    assert current_session is not None, "No se identificó la sesión actual"
    assert current_session["os_family"] == "Windows", f"OS family incorrecto: {current_session['os_family']}"
    print(f"     Sesión actual: id={current_session['session_id']}, os={current_session['os_family']}, browser={current_session['browser_family']}, ip={current_session['ip_address']}")

    # 3. Login session 2 (Mobile iPhone)
    ua_mobile = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
    token_2 = login(admin_a_email, admin_a_pass, user_agent=ua_mobile)
    print("\n[OK] 3. Sesion 2 iniciada (dispositivo móvil secundario).")

    # 4. Check sessions from session 1
    status, sessions_after_2 = api_call("/auth/sessions", token=token_1)
    assert status == 200
    assert len(sessions_after_2) >= 2, f"Esperadas al menos 2 sesiones, encontradas {len(sessions_after_2)}"
    s2 = next((s for s in sessions_after_2 if not s["is_current"] and s["os_family"] == "iOS"), None)
    assert s2 is not None, f"No se encontró la sesión de iOS: {sessions_after_2}"
    print(f"[OK] 4. Inventario muestra 2 sesiones concurrentes. Sesión remota: {s2['session_id']} ({s2['device_family']} / {s2['os_family']})")

    # 5. Revoke session 2 from session 1
    status, revoke_res = api_call(f"/auth/sessions/{s2['session_id']}", method="DELETE", token=token_1)
    assert status in (200, 204), f"Error revocando sesión remota: {status} {revoke_res}"
    print(f"[OK] 5. Sesión remota revocada exitosamente (status={status}).")

    # 6. Verify token 2 is immediately rejected (401)
    status, check_revoked = api_call("/auth/sessions", token=token_2)
    assert status == 401, f"Token 2 debería ser 401 pero devolvió: {status}"
    print(f"[OK] 6. Token 2 rechazado con código 401 (mensaje: {check_revoked.get('detail')})")

    # 7. Verify token 1 remains valid
    status, check_active = api_call("/auth/sessions", token=token_1)
    assert status == 200, f"Token 1 debería seguir activo pero devolvió: {status}"
    print("[OK] 7. Token 1 continúa activo y funcional sin interrupciones.")

    # 8. Cross-tenant / cross-user isolation test
    token_b = login(admin_b_email, admin_b_pass)
    # Admin B tries to revoke Admin A's session 1
    status, cross_revoke = api_call(f"/auth/sessions/{current_session['session_id']}", method="DELETE", token=token_b)
    assert status in (403, 404), f"Aislamiento falló! Devolvió: {status} {cross_revoke}"
    print(f"[OK] 8. Aislamiento estricto verificado: Usuario B no puede revocar sesión de Usuario A (status: {status}).")

    # 9. Revoke other sessions (bulk revocation)
    # Create two additional sessions
    ua_tablet = "Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/605.1.15 Version/16.5 Mobile/15E148 Safari/604.1"
    ua_linux = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36"
    t_tablet = login(admin_a_email, admin_a_pass, user_agent=ua_tablet)
    t_linux = login(admin_a_email, admin_a_pass, user_agent=ua_linux)

    status, list_before_bulk = api_call("/auth/sessions", token=token_1)
    assert len(list_before_bulk) >= 3, f"Esperadas al menos 3 sesiones, hay {len(list_before_bulk)}"
    print(f"\n[OK] 9a. Creadas sesiones concurrentes adicionales. Total activas: {len(list_before_bulk)}.")

    status, bulk_res = api_call("/auth/sessions", method="DELETE", token=token_1)
    assert status == 200, f"Fallo al revocar otras sesiones: {status} {bulk_res}"
    print(f"[OK] 9b. 'Cerrar otras sesiones' ejecutado: {bulk_res}")

    # Verify other tokens are rejected
    s_tablet, _ = api_call("/auth/sessions", token=t_tablet)
    s_linux, _ = api_call("/auth/sessions", token=t_linux)
    assert s_tablet == 401 and s_linux == 401, f"Las otras sesiones deberían ser 401, tablet={s_tablet}, linux={s_linux}"

    # Verify current session is the only active one remaining
    status, list_after_bulk = api_call("/auth/sessions", token=token_1)
    assert len(list_after_bulk) == 1, f"Debería quedar exactamente 1 sesión activa, quedaron {len(list_after_bulk)}"
    print("[OK] 9c. Confirmado: únicamente la sesión actual permanece activa.")

    # 10. Automated cleanup endpoint
    status, cleanup_res = api_call("/auth/sessions/cleanup", method="POST", token=token_1)
    assert status == 403, f"La limpieza debe estar restringida a un operador configurado: {status} {cleanup_res}"
    print("\n[OK] 10. Mantenimiento global bloqueado para usuario no operador (403).")

    print("\n=================================================================")
    print("TODAS LAS VERIFICACIONES DEL PR #8 EN VIVO FUERON EXITOSAS (10/10)")
    print("=================================================================")

if __name__ == "__main__":
    main()
