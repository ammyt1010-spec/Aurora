import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

FRONTEND_URL = "http://127.0.0.1:5177"
OUTPUT_DIR = Path("D:/Colmena2.0-professional/playwright_reports/screenshots_pr7")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with open(".audit_credentials.json", "r", encoding="utf-8") as f:
    CREDS = json.load(f)

EMP_A = CREDS["empresa_a"]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # 1. Login Screen
        context = await browser.new_context(viewport={"width": 1280, "height": 850})
        page = await context.new_page()
        await page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")
        await page.screenshot(path=str(OUTPUT_DIR / "01_login_screen.png"))
        print("[PASS] Captured: 01_login_screen.png")

        # 2. Public Survey Screen (CENSOPAS 112 items)
        survey_url = f"{FRONTEND_URL}/encuesta/{EMP_A['public_survey_id']}"
        await page.goto(survey_url, wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(OUTPUT_DIR / "02_survey_censopas_public.png"))
        print("[PASS] Captured: 02_survey_censopas_public.png")

        # 3. Settings Screen with Enterprise Audit Panel as OWNER
        await page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")
        await page.fill('input[type="email"], input[name="email"]', EMP_A["admin_email"])
        await page.fill('input[type="password"], input[name="password"]', EMP_A["admin_password"])
        await page.click('button[type="submit"]')
        await page.wait_for_function("() => window.location.pathname.startsWith('/colmena')", timeout=15000)
        print("[PASS] Logged in as OWNER")

        # Navigate to Settings
        await page.goto(f"{FRONTEND_URL}/colmena/settings", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(OUTPUT_DIR / "03_settings_owner_audit_panel.png"), full_page=True)
        print("[PASS] Captured: 03_settings_owner_audit_panel.png")

        # Capture Dashboard
        await page.goto(f"{FRONTEND_URL}/colmena", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(OUTPUT_DIR / "04_dashboard_owner.png"))
        print("[PASS] Captured: 04_dashboard_owner.png")

        # Capture Project Results
        await page.goto(f"{FRONTEND_URL}/colmena/project/{EMP_A['project_id']}/results", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(OUTPUT_DIR / "05_project_results.png"))
        print("[PASS] Captured: 05_project_results.png")

        # Capture Reports
        await page.goto(f"{FRONTEND_URL}/colmena/project/{EMP_A['project_id']}/reports", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(OUTPUT_DIR / "06_project_reports.png"))
        print("[PASS] Captured: 06_project_reports.png")

        await context.close()

        # 4. Settings Screen as COLLABORATOR (Audit Panel MUST be hidden)
        context_collab = await browser.new_context(viewport={"width": 1280, "height": 850})
        page_collab = await context_collab.new_page()
        await page_collab.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")
        await page_collab.fill('input[type="email"], input[name="email"]', EMP_A["colaborador_email"])
        await page_collab.fill('input[type="password"], input[name="password"]', EMP_A["colaborador_password"])
        await page_collab.click('button[type="submit"]')
        await page_collab.wait_for_function("() => window.location.pathname.startsWith('/colmena')", timeout=15000)
        print("[PASS] Logged in as COLLABORATOR")

        await page_collab.goto(f"{FRONTEND_URL}/colmena/settings", wait_until="networkidle")
        await page_collab.wait_for_timeout(1500)
        await page_collab.screenshot(path=str(OUTPUT_DIR / "07_settings_collab_audit_hidden.png"), full_page=True)
        print("[PASS] Captured: 07_settings_collab_audit_hidden.png")

        # Check that text 'Historial de actividad empresarial' is NOT present
        body_text = await page_collab.content()
        assert "Historial de actividad empresarial" not in body_text, "Security Breach: Audit panel visible to COLLABORATOR!"
        print("[PASS] Confirmed: Enterprise Audit Panel is completely HIDDEN for COLLABORATOR role.")

        await context_collab.close()
        await browser.close()
        print("\nALL SCREENSHOTS CAPTURED SUCCESSFULLY IN:", OUTPUT_DIR)

if __name__ == "__main__":
    asyncio.run(main())
