import asyncio
import json
import shutil
import sys
from pathlib import Path
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User, Organization
from app.models.project import Project
from app.models.study import Study, StudyUnitType, StudyUnit
from app.models.instrument import Instrument, InstrumentVersion
from app.core.security import create_access_token

FRONTEND_URL = "http://127.0.0.1:5177"
OUTPUT_DIR = Path("D:/Colmena2.0-professional/playwright_reports/screenshots_pr15")
ARTIFACT_SCREENSHOTS_DIR = Path(r"C:\Users\MICELIO SERVER\.gemini\antigravity\brain\c7f89d0d-9c5d-4e78-b566-13ec360b402d\screenshots")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

async def setup_campaign_data():
    print("[*] Setting up enterprise campaign verification data...")
    async with AsyncSessionLocal() as session:
        # Find Empresa A owner
        with open(".audit_credentials.json", "r", encoding="utf-8") as f:
            creds = json.load(f)
        emp_a_email = creds["empresa_a"]["admin_email"]
        proj_id = creds["empresa_a"]["project_id"]
        res = await session.execute(select(User).where(User.email == emp_a_email))
        user_a = res.scalars().first()
        if not user_a:
            print("User A not found in DB")
            return None, None

        token = create_access_token(user_a.id)
        return token, proj_id

async def main():
    token, proj_id = await setup_campaign_data()
    if not token or not proj_id:
        print("[!] Could not prepare tokens for screenshots.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # Inject auth token in localStorage
        await page.goto(f"{FRONTEND_URL}/login")
        await page.evaluate(f"""() => {{
            localStorage.setItem("aurora_token", "{token}");
            localStorage.setItem("token", "{token}");
        }}""")

        # 1. Dashboard and Multidisciplinary Catalog
        print("[*] Navigating to Dashboard and Instruments Catalog...")
        await page.goto(f"{FRONTEND_URL}/app/dashboard")
        await page.wait_for_timeout(2000)

        # Open multidisciplinary catalog drawer if available
        try:
            btn_catalog = page.locator("button:has-text('Explorar Catálogo'), button:has-text('Catálogo')").first
            if await btn_catalog.count() > 0:
                await btn_catalog.click()
                await page.wait_for_timeout(1000)
        except Exception as e:
            print(f"Note on catalog click: {e}")

        catalog_ss = OUTPUT_DIR / "18_pr15_multidisciplinary_catalog.png"
        await page.screenshot(path=str(catalog_ss), full_page=True)
        shutil.copy2(catalog_ss, ARTIFACT_SCREENSHOTS_DIR / "18_pr15_multidisciplinary_catalog.png")
        print(f"[+] Saved {catalog_ss.name}")

        # 2. Project Workspace / Studies
        print(f"[*] Navigating to Project Workspace ({proj_id})...")
        await page.goto(f"{FRONTEND_URL}/projects/{proj_id}")
        await page.wait_for_timeout(2500)

        project_ss = OUTPUT_DIR / "19_pr15_project_campaign_workspace.png"
        await page.screenshot(path=str(project_ss), full_page=True)
        shutil.copy2(project_ss, ARTIFACT_SCREENSHOTS_DIR / "19_pr15_project_campaign_workspace.png")
        print(f"[+] Saved {project_ss.name}")

        # 3. Settings / Enterprise Billing & Invitations Panel
        print("[*] Navigating to Settings Page...")
        await page.goto(f"{FRONTEND_URL}/settings")
        await page.wait_for_timeout(2000)

        settings_ss = OUTPUT_DIR / "20_pr15_settings_enterprise_campaign.png"
        await page.screenshot(path=str(settings_ss), full_page=True)
        shutil.copy2(settings_ss, ARTIFACT_SCREENSHOTS_DIR / "20_pr15_settings_enterprise_campaign.png")
        print(f"[+] Saved {settings_ss.name}")

        await browser.close()
        print("[*] Screenshot capture completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
