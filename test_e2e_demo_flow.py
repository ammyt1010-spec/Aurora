import json
import urllib.request
import urllib.parse
import sys

BASE_URL = "http://localhost:8002/api/v1"

def log(msg):
    print(f"[DEMO TEST] {msg}")

def main():
    log("1. Autenticando usuario demo...")
    req = urllib.request.Request(f"{BASE_URL}/auth/demo-login", method="POST")
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode("utf-8"))
    token = data["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    log("   -> Autenticacion exitosa.")

    log("2. Creando Evaluacion Rapida CENSOPAS Media (112 items)...")
    quick_eval_payload = json.dumps({
        "company_name": "Compania Minera Yauricocha S.A.C.",
        "company_ruc": "20123456789",
        "company_sector": "MINING",
        "instrument_version": "MEDIUM",
        "study_name": "Evaluacion Psicosocial 2026 - Yauricocha",
        "population_invited": 50
    }).encode("utf-8")

    req = urllib.request.Request(f"{BASE_URL}/quick-eval", data=quick_eval_payload, headers=headers, method="POST")
    res = urllib.request.urlopen(req)
    quick_res = json.loads(res.read().decode("utf-8"))
    
    project_id = quick_res["project_id"]
    study_id = quick_res["study_id"]
    public_id = str(quick_res["public_id"])
    survey_url = quick_res["survey_url"]

    log(f"   -> Evaluacion creada: project_id={project_id}, study_id={study_id}")
    log(f"   -> Enlace publico: /encuesta/{public_id}")

    log("3. Obteniendo paquete de preguntas para el trabajador...")
    req = urllib.request.Request(f"{BASE_URL}/public/studies/{public_id}", method="GET")
    res = urllib.request.urlopen(req)
    survey_bundle = json.loads(res.read().decode("utf-8"))
    questions = survey_bundle.get("questions", [])
    log(f"   -> Encuesta cargada: {len(questions)} preguntas totales.")

    log("4. Simulando respuesta de 5 trabajadores...")
    for worker_idx in range(1, 6):
        # Iniciar sesión pública de respuesta
        req = urllib.request.Request(f"{BASE_URL}/public/studies/{public_id}/response-sessions", method="POST")
        res = urllib.request.urlopen(req)
        session_data = json.loads(res.read().decode("utf-8"))
        session_id = session_data["id"]

        # Responder las primeras 20 preguntas
        answers_count = 0
        for q in questions[:20]:
            q_id = q["id"]
            q_type = q.get("question_type", "SINGLE_CHOICE")
            payload = {}
            if q.get("options") and len(q["options"]) > 0:
                opt_id = q["options"][(worker_idx + q_id) % len(q["options"])]["id"]
                payload = {"option_id": opt_id}
            elif q_type == "NUMBER":
                payload = {"numeric_value": 30 + worker_idx}
            elif q_type == "TEXT":
                payload = {"text_value": f"Respuesta trabajador {worker_idx}"}
            else:
                payload = {"boolean_value": True}

            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(f"{BASE_URL}/response-sessions/{session_id}/responses/{q_id}", data=data_bytes, headers={"Content-Type": "application/json"}, method="PUT")
            try:
                urllib.request.urlopen(req)
                answers_count += 1
            except Exception as e:
                pass

        # Completar sesión de respuestas
        complete_bytes = json.dumps({}).encode("utf-8")
        req = urllib.request.Request(f"{BASE_URL}/response-sessions/{session_id}/complete", data=complete_bytes, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req)
        log(f"   -> Trabajador {worker_idx} completo la encuesta ({answers_count} respuestas grabadas).")

    log("5. Verificando Telemetria en Vivo...")
    req = urllib.request.Request(f"{BASE_URL}/projects/{project_id}/telemetry", headers=headers, method="GET")
    res = urllib.request.urlopen(req)
    telemetry_data = json.loads(res.read().decode("utf-8"))
    log(f"   -> Telemetria procesada exitosamente: {json.dumps(telemetry_data)[:120]}...")

    log("6. Generando vista previa de Reporte PDF Oficial SUNAFIL...")
    report_payload = json.dumps({
        "requested_by_user_id": 1,
        "report_mode": "PROVISIONAL",
        "output_format": "PDF",
        "sections": ["portada", "resumen_ejecutivo", "resultados_globales", "dimensiones"]
    }).encode("utf-8")

    req = urllib.request.Request(f"{BASE_URL}/studies/{study_id}/reports/preview", data=report_payload, headers=headers, method="POST")
    res = urllib.request.urlopen(req)
    report_res = json.loads(res.read().decode("utf-8"))

    log(f"   -> Reporte PDF generado exitosamente: preview_id={report_res['preview_id']}, estado={report_res['status']}")
    log("=== PRUEBA DE FLUJO COMPLETO FINALIZADA CON EXITO ===")

if __name__ == "__main__":
    main()
