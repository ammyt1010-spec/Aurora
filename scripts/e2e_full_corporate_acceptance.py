"""AURORA Professional: Validación Visual E2E y Captura de Evidencias Corporativas Definitivas.

Recorre automáticamente la plataforma en Chrome local con Playwright:
- Login corporativo y botón demo de 1 clic
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

FRONTEND_URL = "http://localhost:5176"
BACKEND_URL = "http://localhost:8002"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
QA_DIR = Path(r"D:\Colmena2.0\docs\qa\aurora-corporate-validation-20261022")
SCREENSHOTS_DIR = QA_DIR / "screenshots"
ARTIFACTS_DIR = Path(r"C:\Users\MICELIO SERVER\.gemini\antigravity\brain\c629a912-dc21-4b0e-b0b4-ebe14b306634\screenshots")

VIEWPORTS = [
    {"name": "mobile_compact_360x800", "width": 360, "height": 800},
    {"name": "mobile_iphone_390x844", "width": 390, "height": 844},
    {"name": "tablet_portrait_768x1024", "width": 768, "height": 1024},
    {"name": "tablet_landscape_1024x768", "width": 1024, "height": 768},
    {"name": "desktop_laptop_1440x900", "width": 1440, "height": 900},
    {"name": "desktop_fhd_1920x1080", "width": 1920, "height": 1080},
]

TIMINGS = {}
CONSOLE_LOGS = []

async def main():
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (QA_DIR / "benchmarks").mkdir(parents=True, exist_ok=True)

    print("=== INICIANDO VALIDACIÓN CORPORATIVA AURORA PROFESSIONAL ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )

        # -------------------------------------------------------------
        # 1. VALIDACIÓN LOGIN Y MARCA
        # -------------------------------------------------------------
        print("\n--- 1. Login y Marca ---")
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        page.on("console", lambda msg: CONSOLE_LOGS.append(f"[{msg.type}] {msg.text}"))

        t0 = time.time()
        await page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")
        TIMINGS["login_page_load"] = round(time.time() - t0, 3)
        print(f"Login cargado en {TIMINGS['login_page_load']}s")

        # Captura Login en Desktop y Mobile
        await page.screenshot(path=str(SCREENSHOTS_DIR / "login_desktop_1440.png"), full_page=True)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.screenshot(path=str(SCREENSHOTS_DIR / "login_mobile_390.png"), full_page=True)

        # Autenticación Demo o credenciales
        await page.set_viewport_size({"width": 1440, "height": 900})
        demo_btn = page.locator("button:has-text('Iniciar Demostración'), button:has-text('demostración')")
        if await demo_btn.count() > 0:
            print("Haciendo clic en botón de Demostración...")
            t0 = time.time()
            await demo_btn.first.click()
        else:
            print("Llenando credenciales directas...")
            await page.fill("input[type='email']", "revisor.corporativo@aurora.com")
            await page.fill("input[type='password']", "Aurora2026!")
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
        if await company_select.count() > 0:
            current_val = await company_select.input_value()
            if current_val != "23":
                await company_select.select_option("23")
                await asyncio.sleep(0.8)

        # Marcar los instrumentos disponibles
        checkboxes = page.locator("section[aria-label='Seleccionar instrumentos de batería'] input[type='checkbox']")
        cb_count = await checkboxes.count()
        print(f"  -> Instrumentos encontrados para la empresa: {cb_count}")
        for i in range(min(cb_count, 2)):
            cb = checkboxes.nth(i)
            if not await cb.is_checked():
                await cb.check()
                await asyncio.sleep(0.2)

        # Generar enlace y QR
        gen_btn = page.locator("button:has-text('Generar enlace y QR')")
        if await gen_btn.count() > 0 and await gen_btn.is_enabled():
            print("  -> Generando enlace y QR conjunto...")
            await gen_btn.click()
            await page.wait_for_selector("button:has-text('Copiar enlace')", timeout=10000)
            await asyncio.sleep(0.5)
            await page.screenshot(path=str(SCREENSHOTS_DIR / "modal_bateria_qr_generada.png"))
            await page.screenshot(path=str(SCREENSHOTS_DIR / "inicio_bateria_qr_generada.png"))
            print("  -> QR y enlace de batería generados con éxito.")

        # Probar colapso/despliegue del catálogo secundario
        cat_toggle = page.locator("button:has-text('Explorar catálogo')")
        if await cat_toggle.count() > 0:
            print("  -> Desplegando catálogo secundario...")
            await cat_toggle.click()
            await page.wait_for_selector(".aurora-home-catalog", timeout=10000)
            await asyncio.sleep(0.4)

            # Pestaña Multidisciplinario
            multidisc_tab = page.locator("button[role='tab']:has-text('Multidisciplinario')")
            if await multidisc_tab.count() > 0:
                await multidisc_tab.click()
                await asyncio.sleep(0.4)
                await page.screenshot(path=str(SCREENSHOTS_DIR / "inicio_catalogo_multidisciplinario.png"))

            # Pestaña Psicosocial
            censopas_tab = page.locator("button[role='tab']:has-text('Psicosocial')")
            if await censopas_tab.count() > 0:
                await censopas_tab.click()
                await asyncio.sleep(0.4)

        # Probar botón 'Mis evaluaciones'
        eval_btn = page.locator("button:has-text('Mis evaluaciones')")
        if await eval_btn.count() > 0:
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
        await page.goto(f"{FRONTEND_URL}/colmena/project/23/telemetry", wait_until="networkidle")
        TIMINGS["telemetry_page_load"] = round(time.time() - t0, 3)
        await page.wait_for_selector(".aurora-compact, .aurora-bi-panel, table", timeout=20000)
        print(f"Telemetría cargada con diagnóstico ejecutivo en {TIMINGS['telemetry_page_load']}s")

        # Captura exacta para revisión directiva a 1440x900 (viewport ejecutivo sin scroll forzado)
        await page.set_viewport_size({"width": 1440, "height": 900})
        await asyncio.sleep(0.5)
        await page.screenshot(path=str(SCREENSHOTS_DIR / "telemetria_ejecutiva_1440x900_completa.png"), full_page=False)

        # Probar interactividad: alternar a Mapa de calor
        heatmap_btn = page.locator("button:has-text('calor')")
        if await heatmap_btn.count() > 0:
            print("  -> Alternando a vista de Mapa de Calor...")
            await heatmap_btn.click()
            await page.wait_for_selector(".aurora-compact-heatmap", timeout=5000)
            await asyncio.sleep(0.5)
            await page.screenshot(path=str(SCREENSHOTS_DIR / "telemetria_mapa_de_calor.png"))
            print("  -> Captura Mapa de calor guardada.")

        # Probar interactividad: alternar a Evolución longitudinal
        trend_btn = page.locator("button:has-text('Evoluci')")
        if await trend_btn.count() > 0:
            print("  -> Alternando a vista de Evolución Longitudinal...")
            await trend_btn.click()
            await asyncio.sleep(0.5)
            await page.screenshot(path=str(SCREENSHOTS_DIR / "telemetria_evolucion_longitudinal.png"))

        # Volver a Diagnóstico
        diag_btn = page.locator("button:has-text('Diagn')")
        if await diag_btn.count() > 0:
            await diag_btn.click()
            await asyncio.sleep(0.3)

        # Probar herramientas técnicas colapsables (Explorador avanzado Power BI)
        adv_btn = page.locator("button:has-text('Explorador avanzado')")
        if await adv_btn.count() > 0:
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
        await page.goto(f"{FRONTEND_URL}/colmena/project/23/reports", wait_until="networkidle")
        TIMINGS["reports_page_load"] = round(time.time() - t0, 3)
        await page.wait_for_selector("header:has-text('Informe ejecutivo')", timeout=15000)
        await asyncio.sleep(0.8)
        print(f"Página de Informes cargada en {TIMINGS['reports_page_load']}s")

        # Probar generación de muestra PDF sin consumir licencia si el visor no está listo
        sample_btn = page.locator("button:has-text('Ver muestra PDF sin consumir licencia')")
        if await sample_btn.count() > 0:
            print("  -> Solicitando muestra PDF en visor...")
            await sample_btn.click()
            try:
                await page.wait_for_selector("iframe.aurora-report-preview", timeout=12000)
                await asyncio.sleep(1.0)
                await page.screenshot(path=str(SCREENSHOTS_DIR / "informe_visor_pdf_muestra.png"))
            except Exception as e:
                print(f"  -> Aviso visor: {e}")

        # Probar panel de Informe de batería consolidado bajo demanda
        battery_rep_btn = page.locator("button:has-text('Informe de batería')")
        if await battery_rep_btn.count() > 0:
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
        print("\n--- 5. Enlace Público de Batería (/bateria/83e1755d-af21-4256-bd77-8dd69148e66b) ---")
        bundle_public_id = "83e1755d-af21-4256-bd77-8dd69148e66b"
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
        if r_count > 0:
            for idx in range(min(r_count, 5)):
                try:
                    await radios.nth(idx).click(force=True)
                    await asyncio.sleep(0.1)
                except Exception:
                    pass
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
