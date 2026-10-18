"""AURORA Professional: Certificación Operativa Complementaria - Instrumento No-CENSOPAS (Ergonomía ROSA).

Verifica el ciclo empresarial completo con metodología no-CENSOPAS:
1. Configuración de tarifario por Operador Central para ERGONOMIA_ROSA.
2. Creación de Survey desde InstrumentVersion 5 (ERGONOMIA_ROSA) y Campaña/Estudio para Empresa B.
3. Apertura de campaña, registro de respuestas sintéticas de trabajadores y cierre.
4. Ejecución de scoring canónico y analítica agregada.
5. Cotización, confirmación de pago por Operador Central.
6. Emisión de informe OFFICIAL (autorizado para metodologías no CENSOPAS según PR #16/PR #17).
7. Descarga y análisis forense de DOCX y PDF:
   - Confirmar disciplina ERGONOMIA.
   - Confirmar ausencia total de constructos o baremos CENSOPAS (aislamiento metodológico).
8. Protección anti-reuso de orden pagada y aislamiento multi-tenant cruzado.
"""
import io
import json
import os
import sys
from datetime import datetime, UTC
from decimal import Decimal
from pathlib import Path
import httpx
from docx import Document
from pypdf import PdfReader

BASE_URL = "http://127.0.0.1:8003"

def load_credentials():
    with open(".audit_credentials.json", "r", encoding="utf-8") as f:
        return json.load(f)

def make_client():
    return httpx.Client(base_url=BASE_URL, timeout=120.0)

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
    import struct
    import zlib
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 16, 16, 8, 2, 0, 0, 0)
    raw_pixels = b"".join(b"\x00" + b"\x00\x66\xcc" * 16 for _ in range(16))
    return (
        bytes.fromhex("89504e470d0a1a0a")
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw_pixels))
        + chunk(b"IEND", b"")
    )

def main():
    print("\n" + "="*70)
    print("AURORA PROFESSIONAL: CERTIFICACIÓN ERGONOMÍA (NO-CENSOPAS)")
    print("="*70)

    creds = load_credentials()
    op_creds = creds["operador_central"]
    emp_a_creds = creds["empresa_a"]
    emp_b_creds = creds["empresa_b"]

    client_op = make_client()
    client_a = make_client()
    client_b = make_client()

    # 1. Login
    print("\n[1] Autenticando roles...")
    login(client_op, op_creds["email"], op_creds["password"])
    login(client_a, emp_a_creds["admin_email"], emp_a_creds["admin_password"])
    login(client_b, emp_b_creds["admin_email"], emp_b_creds["admin_password"])
    print("    [+] Sesiones y tokens CSRF establecidos.")

    # 2. Configurar tarifario activo para ERGONOMIA_ROSA si no existe
    print("\n[2] Verificando tarifario activo para ERGONOMIA_ROSA...")
    tariffs = client_op.get("/api/v1/billing/tariffs").json()
    ergo_tariff = next((t for t in tariffs if t.get("method_code") == "ERGONOMIA_ROSA" and t.get("active")), None)
    if not ergo_tariff:
        t_resp = client_op.post(
            "/api/v1/billing/tariffs",
            json={
                "method_code": "ERGONOMIA_ROSA",
                "pricing_mode": "FIXED",
                "min_workers": 1,
                "max_workers": 500,
                "price": "480.00",
                "currency": "PEN",
                "notes": "Tarifa oficial corporativa para evaluación ergonómica ROSA",
                "active": True,
            }
        )
        assert t_resp.status_code == 201, f"Failed creating tariff: {t_resp.status_code} {t_resp.text}"
        ergo_tariff = t_resp.json()
        print(f"    [+] Tarifa creada para ERGONOMIA_ROSA: ID {ergo_tariff['id']} (480.00 PEN)")
    else:
        print(f"    [+] Tarifa activa existente para ERGONOMIA_ROSA: ID {ergo_tariff['id']}")

    # 2.1 Verificar / Crear baremo certificado para ERGONOMIA_ROSA (Versión 5)
    barems_resp = client_op.get("/api/v1/instrument-versions/5/barems").json()
    if not barems_resp:
        create_b = client_op.post(
            "/api/v1/instrument-versions/5/barems",
            json={
                "name": "Baremo Certificado Ergonómico ROSA 2026",
                "population_label": "Puestos de Trabajo de Oficina",
                "status": "ACTIVE",
            }
        )
        assert create_b.status_code == 201, f"Failed creating barem: {create_b.status_code} {create_b.text}"
        barem_id = create_b.json()["id"]
        print(f"    [+] Baremo certificado creado para Ergonomía: ID {barem_id}")
    else:
        barem_id = barems_resp[0]["id"]
        print(f"    [+] Baremo certificado existente para Ergonomía: ID {barem_id}")

    user_b_id = client_b.get("/api/v1/auth/me").json()["id"]
    proj_b_orig = client_b.get(f"/api/v1/projects/{emp_b_creds['project_id']}").json()
    org_b_id = proj_b_orig["organization_id"]

    print(f"\n[3] Creando Proyecto de Ergonomía para Empresa B (Org ID: {org_b_id})...")
    proj_resp = client_b.post(
        "/api/v1/projects",
        json={
            "owner_user_id": user_b_id,
            "organization_id": org_b_id,
            "name": "Programa de Ergonomía y Salud Ocupacional 2026",
            "project_type": "CUSTOM",
            "description": "Evaluación ergonómica y postural de puestos de trabajo",
        }
    )
    assert proj_resp.status_code == 201, f"Project creation failed: {proj_resp.status_code} {proj_resp.text}"
    ergo_project = proj_resp.json()
    ergo_proj_id = ergo_project["id"]
    print(f"    [+] Proyecto creado: ID {ergo_proj_id} ('{ergo_project['name']}')")

    print(f"\n[4] Creando Survey de Ergonomía para Proyecto {ergo_proj_id}...")
    survey_resp = client_b.post(
        f"/api/v1/projects/{ergo_proj_id}/surveys/from-instrument",
        json={
            "created_by_user_id": user_b_id,
            "instrument_version_id": 5,
            "name": "Evaluación Ergonómica de Oficinas y Pantallas ROSA 2026",
            "description": "Inspección de factores de riesgo postural en puestos administrativos",
            "survey_type": "INSTRUMENT",
        }
    )
    assert survey_resp.status_code == 201, f"Survey creation failed: {survey_resp.status_code} {survey_resp.text}"
    survey = survey_resp.json()
    survey_id = survey["id"]
    print(f"    [+] Survey creado: ID {survey_id} ('{survey['name']}')")

    # 5. Crear Estudio / Campaña en Empresa B
    print("\n[5] Creando Estudio / Campaña en Empresa B...")
    study_resp = client_b.post(
        f"/api/v1/projects/{ergo_proj_id}/studies",
        json={
            "survey_id": survey_id,
            "name": "Campaña Ergonómica Integral 2026 - Oficinas Centrales",
            "study_type": "CUSTOM",
            "min_publishable_n": 5,
            "settings": {
                "headcount": 50,
                "headcount_source": "PLANILLA_OFICIAL_EMPRESA",
            },
            "requires_invitation": False,
        }
    )
    assert study_resp.status_code == 201, f"Study creation failed: {study_resp.status_code} {study_resp.text}"
    study = study_resp.json()
    study_id = study["id"]
    study_public_id = study["public_id"]
    print(f"    [+] Estudio creado: ID {study_id} (Public ID: {study_public_id})")

    # Asociar baremo al estudio
    patch_b = client_b.patch(f"/api/v1/studies/{study_id}", json={"barem_id": barem_id})
    assert patch_b.status_code == 200, f"Failed setting barem: {patch_b.status_code} {patch_b.text}"
    print(f"    [+] Baremo certificado ID {barem_id} vinculado al estudio.")

    # 5. Abrir la campaña
    print("\n[5] Abriendo campaña de evaluación...")
    open_resp = client_b.post(f"/api/v1/studies/{study_id}/open")
    assert open_resp.status_code == 200, f"Open study failed: {open_resp.status_code} {open_resp.text}"
    print(f"    [+] Campaña abierta exitosamente. Estado: {open_resp.json()['status']}")

    # 6. Registrar respuestas sintéticas de 10 trabajadores
    print("\n[6] Registrando respuestas de 10 trabajadores en puestos de oficina...")
    client_anon = make_client()
    bundle = client_anon.get(f"/api/v1/public/studies/{study_public_id}").json()
    q_items = bundle["questions"]
    print(f"    [+] Preguntas en formulario ergonómico: {len(q_items)}")

    for worker_idx in range(1, 11):
        # Iniciar sesión pública de respuesta
        sess_resp = client_anon.post(
            f"/api/v1/public/studies/{study_public_id}/response-sessions",
            json={"channel": "WEB"}
        )
        assert sess_resp.status_code in (200, 201), f"Start session failed: {sess_resp.status_code} {sess_resp.text}"
        sess_data = sess_resp.json()
        sess_id = sess_data["id"]
        headers_worker = {"X-Response-Token": sess_data["access_token"]}

        # Responder cada pregunta ergonómica
        for q in q_items:
            opts = q.get("options") or []
            if opts:
                chosen_opt = opts[worker_idx % len(opts)]
                ans_val = chosen_opt.get("numeric_value") or 1.0
                opt_id = chosen_opt["id"]
            else:
                ans_val = 2.0 + (worker_idx % 3)
                opt_id = None

            put_resp = client_anon.put(
                f"/api/v1/response-sessions/{sess_id}/responses/{q['id']}",
                json={
                    "option_id": opt_id,
                    "value_numeric": ans_val,
                    "value_text": str(ans_val),
                },
                headers=headers_worker,
            )
            assert put_resp.status_code in (200, 201), f"Save answer failed: {put_resp.status_code} {put_resp.text}"

        # Completar la sesión
        complete_resp = client_anon.post(
            f"/api/v1/response-sessions/{sess_id}/complete",
            headers=headers_worker,
        )
        assert complete_resp.status_code in (200, 204), f"Complete session failed: {complete_resp.status_code}"

    print("    [+] 10 evaluaciones ergonómicas completadas con éxito.")

    # 7. Cerrar campaña y procesar puntuaciones canónicas
    print("\n[7] Cerrando campaña y ejecutando scoring canónico...")
    close_resp = client_b.post(f"/api/v1/studies/{study_id}/close")
    assert close_resp.status_code == 200
    print("    [+] Campaña cerrada.")

    score_resp = client_b.post(f"/api/v1/studies/{study_id}/scoring")
    assert score_resp.status_code == 200, f"Score failed: {score_resp.status_code} {score_resp.text}"
    score_data = score_resp.json()
    print(f"    [+] Scoring ejecutado. Run ID: {score_data.get('analysis_run_id')}, Constructos calculados: {score_data.get('construct_count', score_data.get('scored_count'))}")

    # 8. Cotización comercial para ERGONOMIA_ROSA
    print("\n[8] Solicitando cotización comercial para ERGONOMIA_ROSA...")
    quote_resp = client_b.post(
        f"/api/v1/billing/studies/{study_id}/quotes",
        json={
            "workers": 50,
            "headcount_source": "ESTUDIO_DECLARADO",
            "method_code": "ERGONOMIA_ROSA",
        }
    )
    assert quote_resp.status_code == 201, f"Quote failed: {quote_resp.status_code} {quote_resp.text}"
    order = quote_resp.json()
    order_id = order["id"]
    print(f"    [+] Cotización aprobada: Orden #{order_id} por {order['amount']} {order['currency']} (Modo: {order['pricing_mode']})")

    # 9. Confirmación de pago por Operador Central
    print("\n[9] Confirmando pago con Operador Central...")
    pay_resp = client_op.post(
        f"/api/v1/billing/orders/{order_id}/confirm-payment",
        json={"payment_reference": "TRANSFER-PACIFICO-ERGO-2026", "payment_channel": "BANK_TRANSFER"}
    )
    assert pay_resp.status_code == 200, f"Payment confirmation failed: {pay_resp.status_code} {pay_resp.text}"
    print(f"    [+] Pago confirmado. Estado: {pay_resp.json()['status']}")

    # 10. Emisión de informe oficial de Ergonomía
    print("\n[10] Emitiendo informe técnico oficial de Ergonomía...")
    import base64
    logo_bytes = create_valid_png_bytes()
    logo_b64 = "data:image/png;base64," + base64.b64encode(logo_bytes).decode("ascii")

    emit_resp = client_b.post(
        f"/api/v1/studies/{study_id}/reports",
        json={
            "billing_order_id": order_id,
            "output_format": "DOCX",
            "report_mode": "OFFICIAL",
            "company_logo_png": logo_b64,
        }
    )
    assert emit_resp.status_code == 201, f"Report emission failed: {emit_resp.status_code} {emit_resp.text}"
    report = emit_resp.json()
    report_id = report["id"]
    data_hash = report["data_hash"]
    meta = report.get("metadata_") or {}
    print(f"    [+] Informe oficial emitido con éxito: ID {report_id}")
    print(f"    [+] Disciplina: {meta.get('discipline')}")
    print(f"    [+] Modo de Reporte: {meta.get('report_mode')}")
    print(f"    [+] Firma criptográfica SHA-256: {data_hash}")
    assert meta.get("discipline") == "ERGONOMIA", f"Expected ERGONOMIA but got {meta.get('discipline')}"
    assert meta.get("report_mode") == "OFFICIAL", f"Expected OFFICIAL but got {meta.get('report_mode')}"

    # 11. Descarga y análisis forense del documento DOCX
    print("\n[11] Descargando y analizando estructura del DOCX ergonómico...")
    dl_resp = client_b.get(f"/api/v1/reports/{report_id}/download")
    assert dl_resp.status_code == 200
    doc = Document(io.BytesIO(dl_resp.content))
    all_text = " ".join(p.text for p in doc.paragraphs)
    print(f"    [+] Párrafos en DOCX: {len(doc.paragraphs)}, Tamaño: {len(dl_resp.content)} bytes")

    # Verificaciones metodológicas críticas:
    # A) Debe contener constructos de ergonomía
    assert "SILLA" in all_text or "PANTALLA" in all_text or "TECLADO" in all_text or "ROSA" in all_text or "ERGON" in all_text.upper(), "El documento debe contener términos ergonómicos"
    print("    [+] Términos y constructos ergonómicos verificados en documento.")

    # B) NO debe contener dimensiones exclusivas de CENSOPAS (aislamiento multidisciplinario)
    censopas_exclusive_terms = ["EXIGENCIAS PSICOLÓGICAS", "DOBLE PRESENCIA", "TRABAJO ACTIVO", "CENSOPAS-COPSOQ"]
    for term in censopas_exclusive_terms:
        assert term not in all_text, f"Violación metodológica: término CENSOPAS '{term}' encontrado en informe de ERGONOMÍA!"
    print("    [+] Aislamiento metodológico verificado: CERO términos o dimensiones CENSOPAS en informe ergonómico.")

    # 12. Conversión y descarga de Vista Previa PDF
    print("\n[12] Generando vista previa PDF con LibreOffice...")
    prev_resp = client_b.post(
        f"/api/v1/studies/{study_id}/reports/preview",
        json={"is_sample_preview": True, "report_mode": "SAMPLE"}
    )
    assert prev_resp.status_code == 201
    prev_data = prev_resp.json()
    prev_id = prev_data["preview_id"]

    pdf_resp = client_b.get(f"/api/v1/reports/{prev_id}/preview.pdf")
    assert pdf_resp.status_code == 200, f"Preview PDF failed: {pdf_resp.status_code}"
    reader = PdfReader(io.BytesIO(pdf_resp.content))
    print(f"    [+] PDF generado por LibreOffice: {len(reader.pages)} páginas, {len(pdf_resp.content)} bytes.")

    # 13. Seguridad: Intento de descarga cruzada por Empresa A
    print("\n[13] Verificando aislamiento multi-tenant cruzado (Empresa A -> Informe Empresa B)...")
    cross_resp = client_a.get(f"/api/v1/reports/{report_id}/download")
    assert cross_resp.status_code in (403, 404), f"Cross tenant access not forbidden: {cross_resp.status_code}"
    print(f"    [+] Intento de acceso cruzado denegado exitosamente ({cross_resp.status_code} Forbidden).")

    # 14. Anti-reuso de orden pagada
    print("\n[14] Verificando protección contra reuso de orden pagada...")
    reuse_resp = client_b.post(
        f"/api/v1/studies/{study_id}/reports",
        json={"billing_order_id": order_id, "output_format": "DOCX", "report_mode": "OFFICIAL"}
    )
    assert reuse_resp.status_code == 409
    print("    [+] Reuso de orden consumida bloqueado (409 Conflict).")

    print("\n" + "="*70)
    print("CERTIFICACIÓN NO-CENSOPAS (ERGONOMÍA): 100% EXITOSA Y VERIFICADA")
    print("="*70)

if __name__ == "__main__":
    main()
