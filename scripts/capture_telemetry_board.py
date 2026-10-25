import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright
from qa_test_support import credentials, isolated_url, required_env

FRONTEND_URL = None  # Set only after explicit isolated QA configuration is validated.
ARTIFACTS_DIR = None
DOCS_DIR = None

async def main():
    global FRONTEND_URL, ARTIFACTS_DIR, DOCS_DIR
    FRONTEND_URL = isolated_url("AURORA_QA_FRONTEND_URL")
    auth = credentials()
    project_id = int(required_env("AURORA_QA_PROJECT_ID"))
    output_dir = Path(required_env("AURORA_QA_OUTPUT_DIR"))
    ARTIFACTS_DIR = output_dir / "artifacts"
    DOCS_DIR = output_dir / "screenshots"
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=os.environ.get("AURORA_QA_CHROME_PATH") or None,
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        print("Navegando al login...")
        await page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")
        
        # Explicit test credentials only: never silently substitute an account for demo.
        await page.fill("input[type='email']", auth["email"])
        await page.fill("input[type='password']", auth["password"])
        await page.click("button[type='submit']")

        await page.wait_for_selector(".aurora-suite-hero, .aurora-home-catalog, .aurora-catalog-card", timeout=15000)
        print("Login completado. Navegando a Telemetría...")

        await page.goto(f"{FRONTEND_URL}/colmena/project/{project_id}/telemetry", wait_until="networkidle")
        await page.wait_for_selector(".aurora-exec-telemetry-root", timeout=15000)
        await asyncio.sleep(1.5)

        # Capturar viewport ejecutivo 1440x900
        shot_1440 = ARTIFACTS_DIR / "telemetria_bi_dashboard_1440x900.png"
        await page.screenshot(path=str(shot_1440), full_page=False)
        await page.screenshot(path=str(DOCS_DIR / "telemetria_bi_dashboard_1440x900.png"), full_page=False)
        print(f"Captura guardada: {shot_1440}")

        # Capturar full page también para verificar alineación completa
        shot_full = ARTIFACTS_DIR / "telemetria_bi_dashboard_fullpage.png"
        await page.screenshot(path=str(shot_full), full_page=True)
        print(f"Captura fullpage guardada: {shot_full}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
