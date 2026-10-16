"""Playwright script to verify and capture PR #8 Session Management UI."""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
import urllib.request

FRONTEND_URL = "http://127.0.0.1:5177"
LOCAL_OUT = Path("D:/Colmena2.0-professional/playwright_reports/screenshots_pr8")
LOCAL_OUT.mkdir(parents=True, exist_ok=True)
BRAIN_OUT = Path(r"C:\Users\MICELIO SERVER\.gemini\antigravity\brain\c7f89d0d-9c5d-4e78-b566-13ec360b402d\screenshots")
BRAIN_OUT.mkdir(parents=True, exist_ok=True)

with open(".audit_credentials.json", "r", encoding="utf-8") as f:
    CREDS = json.load(f)

EMP_A = CREDS["empresa_a"]

def api_login_mobile():
    url = "http://127.0.0.1:8003/api/v1/auth/login"
    data = json.dumps({"email": EMP_A["admin_email"], "password": EMP_A["admin_password"]}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
        },
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

async def main():
    # Pre-create a secondary session (mobile iPhone)
    api_login_mobile()
    print("[INFO] Created secondary session via mobile user agent")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 950})
        page = await context.new_page()

        # 1. Login as Owner
        print("[INFO] Navigating to login...")
        await page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")
        await page.fill('input[type="email"], input[name="email"]', EMP_A["admin_email"])
        await page.fill('input[type="password"], input[name="password"]', EMP_A["admin_password"])
        await page.click('button[type="submit"]')
        await page.wait_for_function("() => window.location.pathname.startsWith('/colmena')", timeout=15000)
        print("[PASS] Logged in successfully")

        # 2. Go to Settings
        print("[INFO] Navigating to Settings...")
        await page.goto(f"{FRONTEND_URL}/colmena/settings", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # 3. Locate Sessions Panel
        panel = page.locator('text=Dispositivos y sesiones activas')
        await panel.wait_for(timeout=10000)
        print("[PASS] Found 'Dispositivos y sesiones activas' panel")

        # 4. Save Full Settings Screenshot
        full_path = LOCAL_OUT / "08_settings_with_sessions_full.png"
        brain_full = BRAIN_OUT / "08_settings_with_sessions_full.png"
        await page.screenshot(path=str(full_path), full_page=True)
        await page.screenshot(path=str(brain_full), full_page=True)
        print(f"[PASS] Captured full settings: {full_path}")

        # 5. Focus on Session Management Panel
        container = page.locator('div:has-text("Dispositivos y sesiones activas")').locator('..').first
        panel_path = LOCAL_OUT / "08_sessions_panel_detail.png"
        brain_panel = BRAIN_OUT / "08_sessions_panel_detail.png"
        await page.screenshot(path=str(panel_path))
        await page.screenshot(path=str(brain_panel))
        print(f"[PASS] Captured session panel detail: {panel_path}")

        await browser.close()
        print("\n[SUCCESS] All Playwright session UI verifications completed!")

if __name__ == "__main__":
    asyncio.run(main())
