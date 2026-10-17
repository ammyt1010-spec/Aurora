import asyncio
import json
import shutil
from pathlib import Path
from playwright.async_api import async_playwright

FRONTEND_URL = "http://127.0.0.1:5177"
OUTPUT_DIR = Path("D:/Colmena2.0-professional/playwright_reports/screenshots_pr12")
ARTIFACT_SCREENSHOTS_DIR = Path(r"C:\Users\MICELIO SERVER\.gemini\antigravity\brain\c7f89d0d-9c5d-4e78-b566-13ec360b402d\screenshots")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

with open(".audit_credentials.json", "r", encoding="utf-8") as f:
    CREDS = json.load(f)

EMP_A = CREDS["empresa_a"]
OP = CREDS["operador_central"]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # 1. Company A Admin View: EnterpriseBillingPanel with Closed Bypass Protection
        context = await browser.new_context(viewport={"width": 1280, "height": 950})
        page = await context.new_page()
        
        print("[1] Logging in as Company A Admin...")
        await page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")
        await page.fill('input[type="email"], input[name="email"]', EMP_A["admin_email"])
        await page.fill('input[type="password"], input[name="password"]', EMP_A["admin_password"])
        await page.click('button[type="submit"]')
        await page.wait_for_function("() => window.location.pathname.startsWith('/colmena')", timeout=15000)
        print("    [+] Logged in as Company A Admin")

        # Navigate to Settings
        await page.goto(f"{FRONTEND_URL}/colmena/settings", wait_until="networkidle")
        await page.wait_for_timeout(2500)

        img1_path = OUTPUT_DIR / "15_pr12_settings_enterprise_billing.png"
        await page.screenshot(path=str(img1_path), full_page=True)
        print(f"    [+] Saved: {img1_path.name}")

        # Detail of the EnterpriseBillingPanel
        billing_panel = page.locator("text=Integridad y Licencias Comerciales").locator("xpath=ancestor::div[contains(@class, 'rounded-2xl')]")
        img2_path = OUTPUT_DIR / "14_pr12_commercial_bypass_closed.png"
        if await billing_panel.count() > 0:
            await billing_panel.first.screenshot(path=str(img2_path))
            print(f"    [+] Saved: {img2_path.name}")
        else:
            await page.screenshot(path=str(img2_path))
            print(f"    [!] Fallback saved: {img2_path.name}")

        await context.close()
        await browser.close()

        # Copy to artifact directory for embedded viewing
        for img in [img1_path, img2_path]:
            if img.exists():
                shutil.copy2(img, ARTIFACT_SCREENSHOTS_DIR / img.name)
                print(f"[+] Copied to artifacts: {img.name}")

        print("\nAll PR #12 Playwright screenshots captured successfully!")


if __name__ == "__main__":
    asyncio.run(main())
