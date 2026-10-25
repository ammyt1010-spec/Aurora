"""AURORA Professional: Validación Visual E2E y Captura de Evidencias Corporativas Definitivas.

Recorre automáticamente la plataforma en Chrome local con Playwright:
- Login con credenciales explícitas de un entorno aislado
- Pantalla 1: Inicio (Catálogo CENSOPAS y multidisciplinario, Mis evaluaciones bajo demanda, Carrito de batería y QR)
- Pantalla 2: Telemetría (Tablero ejecutivo, KPIs, Distribución global de riesgo, Matriz con totales, Interpretación preventiva)
- Pantalla 3: Informe (Previsualización, plantillas, descargas, firma digital SHA-256)
- Enlace público de batería multiinstrumento en formato lista continua (desktop y mobile 390px)
- Inspección responsive en 6 viewports requeridos
- Medición de rendimiento (tiempos de carga, renderizado)
"""
import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright
from qa_test_support import credentials, isolated_url, required_env

FRONTEND_URL = None  # Set only after explicit isolated QA configuration is validated.
QA_DIR = None
SCREENSHOTS_DIR = None
ARTIFACTS_DIR = None

VIEWPORTS = [
    {"name": "mobile_compact_360x800", "width": 360, "height": 800},
    {"name": "mobile_iphone_390x844", "width": 390, "height": 844},
    {"name": "tablet_portrait_768x1024", "width": 768, "height": 1024},
    {"name": "tablet_landscape_1024x768", "width": 1024, "height": 768},
    {"name": "desktop_laptop_1440x900", "width": 1440, "height": 900},
    {"name": "desktop_fhd_1920x1080", "width": 1920, "height": 1080},
]

TIMINGS = {}

async def main():
    global FRONTEND_URL, ARTIFACTS_DIR, QA_DIR, SCREENSHOTS_DIR
    FRONTEND_URL = isolated_url("AURORA_QA_FRONTEND_URL")
    auth = credentials()
    project_id = int(required_env("AURORA_QA_PROJECT_ID"))
    output_dir = Path(required_env("AURORA_QA_OUTPUT_DIR"))
    ARTIFACTS_DIR = output_dir / "artifacts"
    QA_DIR = output_dir
    SCREENSHOTS_DIR = output_dir / "screenshots"
    bundle_public_id = required_env("AURORA_QA_BUNDLE_PUBLIC_ID")
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (QA_DIR / "benchmarks").mkdir(parents=True, exist_ok=True)

    print("=== INICIANDO VALIDACIÓN CORPORATIVA AURORA PROFESSIONAL ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=os.environ.get("AURORA_QA_CHROME_PATH") or None,
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )

        # -------------------------------------------------------------
        # 1. VALIDACIÓN LOGIN Y MARCA
        # -------------------------------------------------------------
        print("\n--- 1. Login y Marca ---")
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # Do not persist browser console payloads; they may contain session data.

        t0 = time.time()
        await page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")
        TIMINGS["login_page_load"] = round(time.time() - t0, 3)
        print(f"Login cargado en {TIMINGS['login_page_load']}s")

        # Captura Login en Desktop y Mobile
        await page.screenshot(path=str(SCREENSHOTS_DIR / "login_desktop_1440.png"), full_page=True)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.screenshot(path=str(SCREENSHOTS_DIR / "login_mobile_390.png"), full_page=True)

        # Autenticación con credenciales de prueba explícitas
        await page.set_viewport_size({"width": 1440, "height": 900})
        # Explicit test credentials only: never silently substitute an account for demo.
        t0 = time.time()
        await page.fill("input[type='email']", auth["email"])
        await page.fill("input[type='password']", auth["password"])
        await page.click("button[type='submit']")

        await page.wait_for_selector(".aurora-suite-hero, .aurora-home-catalog, .aurora-catalog-card", timeout=15000)
        TIMINGS["auth_transition"] = round(time.time() - t0, 3)
        print(f"Autenticación exitosa y carga de Inicio en {TIMINGS['auth_transition']}s")

        # -------------------------------------------------------------
        # 2. PANTALLA 1: INICIO (Batería por casillas y Catálogo colapsable)
        # -------------------------------------------------------------
        print("\n--- 2. Pantalla 1: INICIO ---")
        t0 = time.time()
        await page.goto(f"{FRONTEND_URL}/colmena", wait_until="networkidle")
        TIMINGS["inicio_page_load"] = round(time.time() - t0, 3)
        await page.wait_for_selector("section[aria-label='Seleccionar instrumentos de batería'], .aurora-home-hero", timeout=15000)
        print(f"Inicio cargado en {TIMINGS['inicio_page_load']}s")

        # Seleccionar empresa y generar enlace y QR con casillas de verificación
        print("Probando selección de empresa e instrumentos de batería...")
        company_select = page.locator("select[aria-label='Empresa para la batería']")
        assert await company_select.count() > 0, "Missing required control: company_select"
        current_val = await company_select.input_value()
        if current_val != str(project_id):
            await company_select.select_option(str(project_id))
            await asyncio.sleep(0.8)

        # Marcar los instrumentos disponibles
        checkboxes = page.locator("section[aria-label='Seleccionar instrumentos de batería'] input[type='checkbox']")
        cb_count = await checkboxes.count()
        print(f"  -> Instrumentos encontrados para la empresa: {cb_count}")
        assert cb_count >= 2, "Expected two available instruments"
        for i in range(2):
            cb = checkboxes.nth(i)
            if not await cb.is_checked():
                await cb.check()
                await asyncio.sleep(0.2)

        # Generar enlace y QR
        gen_btn = page.locator("button:has-text('Generar enlace y QR')")
        assert await gen_btn.count() > 0, "Missing required control: gen_btn"
        print("  -> Generando enlace y QR conjunto...")
        await gen_btn.click()
        await page.wait_for_selector("button:has-text('Copiar enlace')", timeout=10000)
        await asyncio.sleep(0.5)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "modal_bateria_qr_generada.png"))
        await page.screenshot(path=str(SCREENSHOTS_DIR / "inicio_bateria_qr_generada.png"))
        print("  -> QR y enlace de batería generados con éxito.")

        # Probar colapso/despliegue del catálogo secundario
        cat_toggle = page.locator("button:has-text('Explorar catálogo')")
        assert await cat_toggle.count() > 0, "Missing required control: cat_toggle"
        print("  -> Desplegando catálogo secundario...")
        await cat_toggle.click()
        await page.wait_for_selector(".aurora-home-catalog", timeout=10000)
        await asyncio.sleep(0.4)

        # Pestaña Multidisciplinario
        multidisc_tab = page.locator("button[role='tab']:has-text('Multidisciplinario')")
        assert await multidisc_tab.count() > 0, "Missing required control: multidisc_tab"
        await multidisc_tab.click()
        await asyncio.sleep(0.4)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "inicio_catalogo_multidisciplinario.png"))

        # Pestaña Psicosocial
        censopas_tab = page.locator("button[role='tab']:has-text('Psicosocial')")
        assert await censopas_tab.count() > 0, "Missing required control: censopas_tab"
        await censopas_tab.click()
        await asyncio.sleep(0.4)

        # Probar botón 'Mis evaluaciones'
        eval_btn = page.locator("button:has-text('Mis evaluaciones')")
        assert await eval_btn.count() > 0, "Missing required control: eval_btn"
        print("  -> Desplegando Mis evaluaciones...")
        await eval_btn.click()
        await asyncio.sleep(0.4)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "inicio_mis_evaluaciones_desplegadas.png"))

        # Recorrer los 6 viewports para Pantalla 1: INICIO
        for vp in VIEWPORTS:
            await page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
            await asyncio.sleep(0.3)
            shot_path = SCREENSHOTS_DIR / f"inicio_{vp['name']}.png"
            await page.screenshot(path=str(shot_path), full_page=True)
            print(f"  -> Captura guardada: {shot_path.name}")

        # -------------------------------------------------------------
        # 3. PANTALLA 2: TELEMETRÍA (Estudio Minero San Cristóbal - Proyecto 23)
        # -------------------------------------------------------------
        print("\n--- 3. Pantalla 2: TELEMETRÍA (Proyecto 23 - Estudio Minero San Cristóbal) ---")
        t0 = time.time()
        await page.goto(f"{FRONTEND_URL}/colmena/project/{project_id}/telemetry", wait_until="networkidle")
        TIMINGS["telemetry_page_load"] = round(time.time() - t0, 3)
        await page.wait_for_selector(".aurora-compact, .aurora-bi-panel, table", timeout=20000)
        print(f"Telemetría cargada con diagnóstico ejecutivo en {TIMINGS['telemetry_page_load']}s")

        # Captura exacta para revisión directiva a 1440x900 (viewport ejecutivo sin scroll forzado)
        await page.set_viewport_size({"width": 1440, "height": 900})
        await asyncio.sleep(0.5)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "telemetria_ejecutiva_1440x900_completa.png"), full_page=False)

        # Probar interactividad: alternar a Mapa de calor
        heatmap_btn = page.locator("button:has-text('calor')")
        assert await heatmap_btn.count() > 0, "Missing required control: heatmap_btn"
        print("  -> Alternando a vista de Mapa de Calor...")
        await heatmap_btn.click()
        await page.wait_for_selector(".aurora-compact-heatmap", timeout=5000)
        await asyncio.sleep(0.5)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "telemetria_mapa_de_calor.png"))
        print("  -> Captura Mapa de calor guardada.")

        # Probar interactividad: alternar a Evolución longitudinal
        trend_btn = page.locator("button:has-text('Evoluci')")
        assert await trend_btn.count() > 0, "Missing required control: trend_btn"
        print("  -> Alternando a vista de Evolución Longitudinal...")
        await trend_btn.click()
        await asyncio.sleep(0.5)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "telemetria_evolucion_longitudinal.png"))

        # Volver a Diagnóstico
        diag_btn = page.locator("button:has-text('Diagn')")
        assert await diag_btn.count() > 0, "Missing required control: diag_btn"
        await diag_btn.click()
        await asyncio.sleep(0.3)

        # Probar herramientas técnicas colapsables (Explorador avanzado Power BI)
        adv_btn = page.locator("button:has-text('Explorador avanzado')")
        assert await adv_btn.count() > 0, "Missing required control: adv_btn"
        print("  -> Desplegando explorador avanzado Power BI...")
        await adv_btn.click()
        await asyncio.sleep(0.6)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "telemetria_explorador_avanzado_powerbi.png"))

        # Captura en los 6 viewports para Pantalla 2: TELEMETRÍA
        for vp in VIEWPORTS:
            await page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
            await asyncio.sleep(0.4)
            shot_path = SCREENSHOTS_DIR / f"telemetria_{vp['name']}.png"
            await page.screenshot(path=str(shot_path), full_page=True)
            print(f"  -> Captura guardada: {shot_path.name}")

        # -------------------------------------------------------------
        # 4. PANTALLA 3: INFORME (Proyecto 23)
        # -------------------------------------------------------------
        print("\n--- 4. Pantalla 3: INFORME (Proyecto 23) ---")
        t0 = time.time()
        await page.goto(f"{FRONTEND_URL}/colmena/project/{project_id}/reports", wait_until="networkidle")
        TIMINGS["reports_page_load"] = round(time.time() - t0, 3)
        await page.wait_for_selector("header:has-text('Informe ejecutivo')", timeout=15000)
        await asyncio.sleep(0.8)
        print(f"Página de Informes cargada en {TIMINGS['reports_page_load']}s")

        # Probar generación de muestra PDF sin consumir licencia si el visor no está listo
        sample_btn = page.locator("button:has-text('Ver muestra PDF sin consumir licencia')")
        assert await sample_btn.count() > 0, "Missing required control: sample_btn"
        print("  -> Solicitando muestra PDF en visor...")
        await sample_btn.click()
        await page.wait_for_selector("iframe.aurora-report-preview", timeout=12000)
        await asyncio.sleep(1.0)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "informe_visor_pdf_muestra.png"))

        # Probar panel de Informe de batería consolidado bajo demanda
        battery_rep_btn = page.locator("button:has-text('Informe de batería')")
        assert await battery_rep_btn.count() > 0, "Missing required control: battery_rep_btn"
        print("  -> Desplegando panel de Informe de Batería...")
        await battery_rep_btn.click()
        await asyncio.sleep(0.6)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "informe_bateria_consolidado.png"))

        # Captura en los 6 viewports para Pantalla 3: INFORME
        for vp in VIEWPORTS:
            await page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
            await asyncio.sleep(0.3)
            shot_path = SCREENSHOTS_DIR / f"informe_{vp['name']}.png"
            await page.screenshot(path=str(shot_path), full_page=True)
            print(f"  -> Captura guardada: {shot_path.name}")

        # -------------------------------------------------------------
        # 5. ENLACE PÚBLICO DE BATERÍA MULTIINSTRUMENTO (Experiencia Colaborador)
        # -------------------------------------------------------------
        print("\n--- 5. Enlace Público de Batería de prueba ---")
        t0 = time.time()
        await page.goto(f"{FRONTEND_URL}/bateria/{bundle_public_id}", wait_until="networkidle")
        TIMINGS["public_bundle_load"] = round(time.time() - t0, 3)
        await page.wait_for_selector("main header, .aurora-survey-card, input[type='radio']", timeout=15000)
        print(f"Página pública de batería cargada en {TIMINGS['public_bundle_load']}s")

        await page.set_viewport_size({"width": 1440, "height": 900})
        await page.screenshot(path=str(SCREENSHOTS_DIR / "bateria_publica_desktop_1440.png"), full_page=True)

        await page.set_viewport_size({"width": 390, "height": 844})
        await page.screenshot(path=str(SCREENSHOTS_DIR / "bateria_publica_mobile_390.png"), full_page=True)

        # Responder interactivamente algunas preguntas en formato continuo
        print("  -> Respondiendo interactivamente en formato continuo...")
        radios = page.locator("input[type='radio']")
        r_count = await radios.count()
        assert r_count > 0, "Expected public questionnaire answer controls"
        if r_count > 0:
            for idx in range(min(r_count, 5)):
                await radios.nth(idx).check()
                assert await radios.nth(idx).is_checked()
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.5)
            await page.screenshot(path=str(SCREENSHOTS_DIR / "cuestionario_colaborador_continuo_mobile.png"))

        await browser.close()

    # Copiar evidencias al directorio de artefactos para renderizado directo
    print("\n--- Copiando capturas al directorio de artefactos ---")
    copied = 0
    for f in SCREENSHOTS_DIR.glob("*.png"):
        shutil.copy2(f, ARTIFACTS_DIR / f.name)
        copied += 1
    print(f"Total {copied} capturas copiadas a: {ARTIFACTS_DIR}")

    # Guardar métricas de timings y logs
    metrics_path = QA_DIR / "benchmarks" / "timings_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(TIMINGS, f, indent=2)
    print(f"Métricas guardadas en: {metrics_path}")

    print("\n=== VALIDACIÓN VISUAL Y DE FLUJOS COMPLETADA EXITOSAMENTE ===")

if __name__ == "__main__":
    asyncio.run(main())
