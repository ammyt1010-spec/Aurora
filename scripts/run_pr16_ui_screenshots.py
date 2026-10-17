import asyncio
import json
import shutil
import sys
from pathlib import Path
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import create_access_token

FRONTEND_URL = "http://127.0.0.1:5173"
OUTPUT_DIR = Path("D:/Colmena2.0-professional/playwright_reports/screenshots_pr16")
ARTIFACT_DIR = Path(r"C:\Users\MICELIO SERVER\.gemini\antigravity\brain\8aef44df-d44d-493d-a9f6-740dbef4cd8e\screenshots")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

async def setup_auth_data():
    async with AsyncSessionLocal() as session:
        creds_file = Path(".audit_credentials.json")
        if not creds_file.exists():
            return None, None
        with open(creds_file, "r", encoding="utf-8") as f:
            creds = json.load(f)
        emp_a_email = creds["empresa_a"]["admin_email"]
        proj_id = creds["empresa_a"]["project_id"]
        res = await session.execute(select(User).where(User.email == emp_a_email))
        user_a = res.scalars().first()
        if not user_a:
            return None, None
        token = create_access_token(user_a.id)
        return token, proj_id

async def main():
    token, proj_id = await setup_auth_data()
    if not token:
        print("[!] Token could not be generated.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # Set localStorage credentials
        await page.goto(f"{FRONTEND_URL}/login")
        await page.evaluate(f"""() => {{
            localStorage.setItem("aurora_token", "{token}");
            localStorage.setItem("token", "{token}");
        }}""")

        # 1. Reports Module / Project Reports Page
        print("[*] Navigating to Reports Workspace...")
        await page.goto(f"{FRONTEND_URL}/projects/{proj_id}/reports")
        await page.wait_for_timeout(2500)
        ss1 = OUTPUT_DIR / "21_pr16_project_reports_workspace.png"
        await page.screenshot(path=str(ss1), full_page=True)
        shutil.copy2(ss1, ARTIFACT_DIR / "21_pr16_project_reports_workspace.png")
        print(f"[+] Saved {ss1.name}")

        # 2. Executive Dashboard Tab / Premium Dashboard
        print("[*] Navigating to Premium Executive Dashboard...")
        await page.goto(f"{FRONTEND_URL}/projects/{proj_id}/dashboard")
        await page.wait_for_timeout(2500)
        ss2 = OUTPUT_DIR / "22_pr16_executive_dashboard_signals.png"
        await page.screenshot(path=str(ss2), full_page=True)
        shutil.copy2(ss2, ARTIFACT_DIR / "22_pr16_executive_dashboard_signals.png")
        print(f"[+] Saved {ss2.name}")

        # 3. Settings / Enterprise Billing and Reports Panel
        print("[*] Navigating to Settings & Reports History...")
        await page.goto(f"{FRONTEND_URL}/settings")
        await page.wait_for_timeout(2000)
        ss3 = OUTPUT_DIR / "23_pr16_enterprise_settings_history.png"
        await page.screenshot(path=str(ss3), full_page=True)
        shutil.copy2(ss3, ARTIFACT_DIR / "23_pr16_enterprise_settings_history.png")
        print(f"[+] Saved {ss3.name}")

        await browser.close()
        print("[+] PR 16 UI Screenshot capture completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
