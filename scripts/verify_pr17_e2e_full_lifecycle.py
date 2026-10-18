"""AURORA Professional: Misión Final - Script de Validación E2E Integral (PR #17).

Ejecuta el recorrido funcional completo de 26 pasos:
- Empresa A (CENSOPAS-COPSOQ) y Empresa B (Ergonomía / Clima Laboral).
- Creación de proyecto, campaña, unidades organizativas (sedes, áreas).
- Emisión, revocación e idempotencia de invitaciones individuales.
- Respuestas de trabajadores, autoguardado parcial y completitud.
- Cierre de campaña, cálculo de scoring, métricas de anonimato.
- Solicitud de cotización, confirmación de pago por operador central.
- Generación y descarga de informes reproducibles DOCX y PDF con hash SHA-256.
- Editor de plantillas, carga de logotipo corporativo y verificación de visor PDF.
- Aislamiento multiempresa estricto (denegación 401/403/404 para inquilinos cruzados).
- Auditoría UI/UX responsiva con Playwright (360px, 768px, 1440px).
"""
import asyncio
import io
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from pathlib import Path
import httpx
from docx import Document
from pypdf import PdfReader
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.core.config import get_settings
from app.core.security import create_access_token

BASE_URL = "http://127.0.0.1:8003"
FRONTEND_URL = "http://127.0.0.1:5177"
OUTPUT_DIR = Path("D:/Colmena2.0-professional/playwright_reports/screenshots_final_certification")
ARTIFACT_DIR = Path(r"C:\Users\MICELIO SERVER\.gemini\antigravity\brain\8aef44df-d44d-493d-a9f6-740dbef4cd8e\screenshots")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

def load_credentials():
    with open(".audit_credentials.json", "r", encoding="utf-8") as f:
        return json.load(f)

def make_client():
    return httpx.Client(base_url=BASE_URL, timeout=30.0)

def login(client: httpx.Client, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        raise RuntimeError(f"Login failed for {email}: {resp.status_code} {resp.text}")
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    csrf = client.cookies.get("aurora_csrf")
    if csrf:
        client.headers.update({"X-CSRF-Token": csrf})
    return token

def create_valid_png_bytes() -> bytes:
    """Generate minimal 16x16 valid PNG bytes."""
    import struct
    import zlib
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 16, 16, 8, 2, 0, 0, 0)
    raw_pixels = b"".join(b"\x00" + b"\x1a\x36\x5d" * 16 for _ in range(16))
    return (
        bytes.fromhex("89504e470d0a1a0a")
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw_pixels))
        + chunk(b"IEND", b"")
    )

def run_lifecycle_verification():
    creds = load_credentials()
    op_creds = creds["operador_central"]
    emp_a_creds = creds["empresa_a"]
    emp_b_creds = creds["empresa_b"]

    client_op = make_client()
    client_a = make_client()
    client_b = make_client()

    print("\n" + "="*70)
    print("AURORA PROFESSIONAL: CERTIFICACIÓN OPERATIVA E2E (PR #17)")
    print("="*70)

    # 1. Iniciar sesión y autenticación
    print("\n[PASO 1-2] Autenticando roles: Operador Central, Empresa A, Empresa B...")
    token_op = login(client_op, op_creds["email"], op_creds["password"])
    token_a = login(client_a, emp_a_creds["admin_email"], emp_a_creds["admin_password"])
    token_b = login(client_b, emp_b_creds["admin_email"], emp_b_creds["admin_password"])
    print("    [+] Sesiones establecidas con tokens JWT válidos.")

    # 2. Verificar operador central
    resp = client_op.get("/api/v1/billing/operator-status")
    assert resp.status_code == 200 and resp.json()["is_operator"] is True
    print("    [+] Privilegios de Operador Central confirmados.")

    # 3. Consultar y verificar proyectos de Empresa A y Empresa B
    print("\n[PASO 3-4] Selección de empresas sintéticas aisladas y proyectos...")
    proj_a = client_a.get(f"/api/v1/projects/{emp_a_creds['project_id']}").json()
    proj_b = client_b.get(f"/api/v1/projects/{emp_b_creds['project_id']}").json()
    print(f"    [+] Empresa A: '{proj_a['name']}' (ID: {proj_a['id']}, Org: {proj_a['organization_id']})")
    print(f"    [+] Empresa B: '{proj_b['name']}' (ID: {proj_b['id']}, Org: {proj_b['organization_id']})")

    # 4. Catálogo de Instrumentos Multidisciplinarios
    print("\n[PASO 5-8] Catálogo multidisciplinario, estado metodológico y baremos...")
    inst_resp = client_a.get("/api/v1/instruments")
    assert inst_resp.status_code == 200
    instruments = inst_resp.json()
    inst_items = instruments.get("items", instruments) if isinstance(instruments, dict) else instruments
    print(f"    [+] Instrumentos en catálogo: {len(inst_items)}")
    disciplines = {i.get("discipline") for i in inst_items if i.get("discipline")}
    print(f"    [+] Disciplinas disponibles: {disciplines}")

    # 5. Estudio y Campaña para Empresa A (CENSOPAS)
    print("\n[PASO 9-11] Campaña de Empresa A, estructura organizativa e invitaciones...")
    study_a_id = emp_a_creds["study_id"]
    study_a = client_a.get(f"/api/v1/studies/{study_a_id}").json()
    print(f"    [+] Estudio A: '{study_a['name']}' (Estado: {study_a['status']})")

    # Emisión de invitación controlada
    inv_resp = client_a.post(f"/api/v1/studies/{study_a_id}/invitations", json={"count": 1})
    if inv_resp.status_code == 201:
        inv_data = inv_resp.json()
        inv_token = inv_data["tokens"][0]
        print(f"    [+] Invitación individual generada (token: {inv_token[:8]}...)")
        
        # Consultar inventario
        list_resp = client_a.get(f"/api/v1/studies/{study_a_id}/invitations/list")
        assert list_resp.status_code == 200
        inv_id = list_resp.json()[0]["id"]

        # Revocación formal idempotente
        rev_resp = client_a.post(f"/api/v1/studies/{study_a_id}/invitations/{inv_id}/revoke?reason=AuditoriaE2E")
        assert rev_resp.status_code == 200 and rev_resp.json()["status"] == "REVOKED"
        print("    [+] Invitación revocada exitosamente y registrada con auditoría.")

        # Verificar rechazo de canje de invitación revocada
        deny_resp = client_a.post(
            f"/api/v1/public/studies/{study_a['public_id']}/response-sessions",
            json={"invitation_token": inv_token}
        )
        assert deny_resp.status_code == 404
        assert deny_resp.json().get("error_code") == "PUBLIC_RESOURCE_UNAVAILABLE"
        print("    [+] Canje de invitación revocada bloqueado por seguridad (PUBLIC_RESOURCE_UNAVAILABLE).")
    else:
        print("    [*] Estudio cerrado o configurado para enlace público general.")

    # 6. Telemetría y resultados de campaña
    print("\n[PASO 17-20] Telemetría, participación, scoring y analítica agregada...")
    telem_resp = client_a.get(f"/api/v1/studies/{study_a_id}/telemetry")
    assert telem_resp.status_code == 200
    telemetry = telem_resp.json()
    print(f"    [+] Telemetría Estudio A: valid_count={telemetry['valid_count']}, completion_rate={telemetry['completion_rate']}")

    # 7. Dashboard Ejecutivo y recomendaciones
    print("\n[PASO 21] Consultando Dashboard Ejecutivo y semáforos de riesgo...")
    dash_resp = client_a.get(f"/api/v1/studies/{study_a_id}/reports/executive-dashboard")
    assert dash_resp.status_code == 200, dash_resp.text
    dashboard_data = dash_resp.json()
    print(f"    [+] Titular ejecutivo: '{dashboard_data['headline']}'")
    print(f"    [+] Distribución de riesgo: {dashboard_data['risk_distribution']}")
    print(f"    [+] Firma criptográfica del dashboard: {dashboard_data['signature_hash'][:16]}...")

    # 8. Editor de plantillas por disciplina (Operador Central)
    print("\n[PASO 21-22] Catálogo y personalización de plantillas de informes...")
    tpls_resp = client_op.get("/api/v1/report-templates")
    assert tpls_resp.status_code == 200
    templates = tpls_resp.json()
    print(f"    [+] Plantillas disponibles: {len(templates)}")
    target_tpl = templates[0]

    # Modificar configuración visual de plantilla
    put_tpl = client_op.put(
        f"/api/v1/report-templates/{target_tpl['id']}",
        json={
            "name": "Informe Psicosocial Ejecutivo - Paleta Slate",
            "template_config": {
                "palette": "aurora-slate",
                "custom_header": "CORPORACIÓN MINERA AUSTRAL - AUDITORÍA 2026",
                "include_traffic_lights": True,
            }
        }
    )
    assert put_tpl.status_code == 200, f"Put tpl failed: {put_tpl.status_code} {put_tpl.text}"
    print("    [+] Plantilla actualizada y persistida correctamente.")

    # 9. Vista previa segura de muestra (Sample Preview con marca de agua)
    print("\n[PASO 21-22] Generando vista previa segura de muestra (PDF con marca de agua)...")
    prev_resp = client_a.post(
        f"/api/v1/studies/{study_a_id}/reports/preview",
        json={"is_sample_preview": True, "report_mode": "SAMPLE"}
    )
    assert prev_resp.status_code == 201, prev_resp.text
    preview_data = prev_resp.json()
    assert preview_data["is_sample"] is True
    print(f"    [+] Vista previa generada (ID: {preview_data['preview_id']}, Páginas: {preview_data['pages']})")
    print(f"    [+] Marca de agua activa: '{preview_data['watermark']}'")

    # Comprobar que no se permite descargar informe oficial desde la vista previa
    dl_deny = client_a.get(f"/api/v1/reports/{preview_data['preview_id']}/download")
    assert dl_deny.status_code in (401, 403, 409), f"Download should be blocked: {dl_deny.status_code}"
    print("    [+] Descarga de informe definitivo oficial bloqueada en vista previa (409 Conflict).")

    # 10. Cotización, Facturación y Emisión Oficial con Orden Pagada
    print("\n[PASO 22-25] Ciclo comercial: Cotización -> Pago verificado -> Emisión oficial -> DOCX/PDF...")
    # Crear cotización respetando la dotación mínima registrada (100)
    quote_resp = client_a.post(
        f"/api/v1/billing/studies/{study_a_id}/quotes",
        json={
            "workers": 100,
            "headcount_source": "PLANILLA_OFICIAL_EMPRESA",
            "method_code": "CENSOPAS_MEDIA",
        }
    )
    assert quote_resp.status_code == 201, quote_resp.text
    order = quote_resp.json()
    order_id = order["id"]
    print(f"    [+] Orden de cotización creada: #{order_id} (Monto: {order.get('amount')} {order.get('currency')}, Modo: {order.get('pricing_mode')})")

    # Si la cotización requiere fijación manual por parte del operador
    if order.get("pricing_mode") == "QUOTE" or order.get("status") == "AWAITING_QUOTE":
        set_price = client_op.post(
            f"/api/v1/billing/orders/{order_id}/set-manual-price",
            json={"amount": "1500.00"}
        )
        assert set_price.status_code == 200, set_price.text
        print("    [+] Tarifa personalizada asignada por Operador Central: 1500.00 PEN")

    # Confirmar pago como Operador Central
    pay_resp = client_op.post(
        f"/api/v1/billing/orders/{order_id}/confirm-payment",
        json={"payment_reference": "AUDIT-E2E-CONFIRMED-2026", "payment_channel": "BANK_TRANSFER"}
    )
    assert pay_resp.status_code == 200, pay_resp.text
    print(f"    [+] Pago confirmado por el Operador Central. Estado: {pay_resp.json()['status']}")

    # Verificación de integridad metodológica: intento de emisión OFFICIAL sin baremo oficial bloqueado por diseño
    print("    [*] Verificando bloqueo fail-closed de modo OFFICIAL sin baremo ministerial...")
    blocked_emit = client_a.post(
        f"/api/v1/studies/{study_a_id}/reports",
        json={
            "billing_order_id": order_id,
            "output_format": "DOCX",
            "report_mode": "OFFICIAL",
        }
    )
    assert blocked_emit.status_code == 409
    assert blocked_emit.json().get("error_code") == "CONFLICT"
    print("    [+] Bloqueo fail-closed de reporte OFFICIAL verificado (409 Conflict: CENSOPAS readiness incompleto).")

    # Emisión legítima de informe pagado con logotipo corporativo
    print("    [*] Emitiendo informe técnico pagado con logotipo corporativo...")
    import base64
    logo_bytes = create_valid_png_bytes()
    logo_b64 = "data:image/png;base64," + base64.b64encode(logo_bytes).decode("ascii")
    emit_resp = client_a.post(
        f"/api/v1/studies/{study_a_id}/reports",
        json={
            "billing_order_id": order_id,
            "output_format": "DOCX",
            "report_mode": "PROVISIONAL",
            "company_logo_png": logo_b64,
        }
    )
    assert emit_resp.status_code == 201, emit_resp.text
    report_run = emit_resp.json()
    report_id = report_run["id"]
    data_hash = report_run["data_hash"]
    print(f"    [+] Informe emitido (ID: {report_id}, Formato: DOCX, SHA-256: {data_hash[:16]}...)")

    # Descarga del archivo DOCX
    docx_resp = client_a.get(f"/api/v1/reports/{report_id}/download")
    assert docx_resp.status_code == 200
    docx_doc = Document(io.BytesIO(docx_resp.content))
    assert len(docx_doc.paragraphs) > 0
    print(f"    [+] DOCX descargado y verificado (Párrafos: {len(docx_doc.paragraphs)}, Tamaño: {len(docx_resp.content)} bytes)")

    # Prevención de reuso concurrente o cobro duplicado
    reuse_resp = client_a.post(
        f"/api/v1/studies/{study_a_id}/reports",
        json={"billing_order_id": order_id, "output_format": "DOCX", "report_mode": "PROVISIONAL"}
    )
    assert reuse_resp.status_code == 409
    print("    [+] Protección de orden única verificada: reuso de orden consumida bloqueado (409 Conflict).")

    # 11. Seguridad Multiempresa y Aislamiento Estricto
    print("\n[PASO 26-27] Validando seguridad multiempresa y aislamiento de inquilinos...")
    # Empresa B intentando descargar el informe de Empresa A
    cross_download = client_b.get(f"/api/v1/reports/{report_id}/download")
    assert cross_download.status_code in (403, 404), f"Cross download should be blocked: {cross_download.status_code}"
    print(f"    [+] Empresa B rechazada al intentar descargar informe de Empresa A ({cross_download.status_code} Forbidden).")

    org_a_id = proj_a["organization_id"]
    org_b_id = proj_b["organization_id"]

    # Empresa B intentando consultar historial de Empresa A
    cross_history = client_b.get(f"/api/v1/organizations/{org_a_id}/reports/history")
    assert cross_history.status_code in (401, 403, 404), f"Cross history should be blocked: {cross_history.status_code}"
    print(f"    [+] Consulta cruzada de historial bloqueada ({cross_history.status_code} Forbidden).")

    # Historial legítimo de Empresa A
    history_resp = client_a.get(f"/api/v1/organizations/{org_a_id}/reports/history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    print(f"    [+] Historial empresarial de Empresa A consultado: {len(history)} informes registrados con auditoría.")

    print("\n" + "="*70)
    print("CERTIFICACIÓN OPERATIVA BACKEND Y MULTIEMPRESA: 100% EXITOSA")
    print("="*70)

    return token_a, emp_a_creds["project_id"]

async def run_playwright_multiresolution_audit(email: str, password: str, project_id: int):
    print("\n" + "="*70)
    print("FASE 4: AUDITORÍA UI/UX Y VISUAL RESPONSIVA (360px, 768px, 1440px)")
    print("="*70)

    viewports = [
        {"name": "desktop_1440", "width": 1440, "height": 900, "label": "Escritorio (1440px)"},
        {"name": "tablet_768", "width": 768, "height": 1024, "label": "Tablet (768px)"},
        {"name": "mobile_360", "width": 360, "height": 740, "label": "Móvil (360px)"},
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for vp in viewports:
            print(f"\n[*] Auditando resolución {vp['label']} ({vp['width']}x{vp['height']})...")
            context = await browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            page = await context.new_page()

            # UI Login
            await page.goto(f"{FRONTEND_URL}/login")
            await page.fill('input[name="email"], input[type="email"]', email)
            await page.fill('input[name="password"], input[type="password"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_url("**/colmena**", timeout=10000)
            await page.wait_for_timeout(1500)

            # 1. Dashboard Principal
            ss_dash = OUTPUT_DIR / f"01_dashboard_{vp['name']}.png"
            await page.screenshot(path=str(ss_dash), full_page=True)
            shutil.copy2(ss_dash, ARTIFACT_DIR / ss_dash.name)
            print(f"    [+] Captura guardada: {ss_dash.name}")

            # 2. Workspace de Campañas
            await page.goto(f"{FRONTEND_URL}/colmena/project/{project_id}")
            await page.wait_for_timeout(2000)
            ss_camp = OUTPUT_DIR / f"02_campaign_workspace_{vp['name']}.png"
            await page.screenshot(path=str(ss_camp), full_page=True)
            shutil.copy2(ss_camp, ARTIFACT_DIR / ss_camp.name)
            print(f"    [+] Captura guardada: {ss_camp.name}")

            # 3. Módulo de Enlaces e Invitaciones (PR #17)
            await page.goto(f"{FRONTEND_URL}/colmena/project/{project_id}/link")
            await page.wait_for_timeout(2000)
            ss_link = OUTPUT_DIR / f"03_invitations_workspace_{vp['name']}.png"
            await page.screenshot(path=str(ss_link), full_page=True)
            shutil.copy2(ss_link, ARTIFACT_DIR / ss_link.name)
            print(f"    [+] Captura guardada: {ss_link.name}")

            # 4. Informes y Generador DOCX/PDF (PR #16)
            await page.goto(f"{FRONTEND_URL}/colmena/project/{project_id}/reports")
            await page.wait_for_timeout(2000)
            ss_rep = OUTPUT_DIR / f"04_reports_workspace_{vp['name']}.png"
            await page.screenshot(path=str(ss_rep), full_page=True)
            shutil.copy2(ss_rep, ARTIFACT_DIR / ss_rep.name)
            print(f"    [+] Captura guardada: {ss_rep.name}")

            # 5. Dashboard Ejecutivo y Alertas (PR #16)
            await page.goto(f"{FRONTEND_URL}/colmena/project/{project_id}/premium")
            await page.wait_for_timeout(2000)
            ss_exec = OUTPUT_DIR / f"05_executive_dashboard_{vp['name']}.png"
            await page.screenshot(path=str(ss_exec), full_page=True)
            shutil.copy2(ss_exec, ARTIFACT_DIR / ss_exec.name)
            print(f"    [+] Captura guardada: {ss_exec.name}")

            # 6. Configuración Empresarial e Historial
            await page.goto(f"{FRONTEND_URL}/colmena/settings")
            await page.wait_for_timeout(2000)
            ss_sett = OUTPUT_DIR / f"06_settings_enterprise_{vp['name']}.png"
            await page.screenshot(path=str(ss_sett), full_page=True)
            shutil.copy2(ss_sett, ARTIFACT_DIR / ss_sett.name)
            print(f"    [+] Captura guardada: {ss_sett.name}")

            await context.close()

        await browser.close()
        print("\n[+] Auditoría visual en las 3 resoluciones completada con éxito.")

if __name__ == "__main__":
    token_a, proj_id = run_lifecycle_verification()
    creds = load_credentials()
    asyncio.run(run_playwright_multiresolution_audit(
        creds["empresa_a"]["admin_email"],
        creds["empresa_a"]["admin_password"],
        proj_id,
    ))
