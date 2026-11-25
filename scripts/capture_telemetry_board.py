import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:5176"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ARTIFACTS_DIR = Path(r"C:\Users\MICELIO SERVER\.gemini\antigravity\brain\c629a912-dc21-4b0e-b0b4-ebe14b306634\screenshots")
DOCS_DIR = Path(r"D:\Colmena2.0\docs\qa\aurora-corporate-validation-20261022\screenshots")

async def main():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        print("Navegando al login...")
        await page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")
        
        # Click demo button or login
        demo_btn = page.locator("button:has-text('Iniciar Demostración'), button:has-text('demostración')")
        if await demo_btn.count() > 0:
            await demo_btn.first.click()
        else:
            await page.fill("input[type='email']", "revisor.corporativo@aurora.com")
            await page.fill("input[type='password']", "Aurora2026!")
            await page.click("button[type='submit']")

        await page.wait_for_selector(".aurora-suite-hero, .aurora-home-catalog, .aurora-catalog-card", timeout=15000)
        print("Login completado. Navegando a Telemetría...")

        await page.goto(f"{FRONTEND_URL}/colmena/project/23/telemetry", wait_until="networkidle")
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
