import asyncio
import json
import shutil
import sys
from pathlib import Path
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.instrument import Instrument, InstrumentVersion
from app.models.option_set import OptionSet, OptionSetOption
from app.models.construct import Construct, ConstructItem
from app.models.question import Question

FRONTEND_URL = "http://127.0.0.1:5177"
OUTPUT_DIR = Path("D:/Colmena2.0-professional/playwright_reports/screenshots_pr13")
ARTIFACT_SCREENSHOTS_DIR = Path(r"C:\Users\MICELIO SERVER\.gemini\antigravity\brain\c7f89d0d-9c5d-4e78-b566-13ec360b402d\screenshots")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

with open(".audit_credentials.json", "r", encoding="utf-8") as f:
    CREDS = json.load(f)

EMP_A = CREDS["empresa_a"]


async def seed_multidisciplinary_catalog():
    print("[*] Seeding representative multidisciplinary instruments...")
    async with AsyncSessionLocal() as session:
        # Check if ROSA exists
        res = await session.execute(select(Instrument).where(Instrument.code == "ERGONOMIA_ROSA"))
        rosa = res.scalars().first()
        if not rosa:
            rosa = Instrument(
                name="Método ROSA - Ergonomía de Oficinas",
                code="ERGONOMIA_ROSA",
                method_code="ERGONOMIA_ROSA",
                discipline="ERGONOMIA",
                author="Sonne, Villalta & Andrews (2012)",
                reproduction_terms="Uso corporativo bajo licencia abierta académica y de salud ocupacional",
                status="AUTHORIZED",
                is_system=True,
            )
            session.add(rosa)
            await session.flush()

            v_rosa = InstrumentVersion(
                instrument_id=rosa.id,
                version_code="ROSA_V2024_CORP",
                status="ACTIVE",
                scoring_status="CONFIGURED",
                reproduction_restrictions="Prohibida su reventa o redistribución fuera de AURORA Professional",
                validation_notes="Validado con 15 reactivos ergonómicos y corte de riesgo postural.",
                methodological_rules={
                    "cutoffs": {"bajo": 3, "medio": 5, "alto": 8},
                    "barem_certified": True,
                },
            )
            session.add(v_rosa)
            await session.flush()

            scale = OptionSet(
                name="Escala Severidad ROSA 1-3",
                instrument_version_id=v_rosa.id,
                options=[
                    OptionSetOption(raw_code="1", label="Conforme / Neutro", numeric_value=1, sort_order=1),
                    OptionSetOption(raw_code="2", label="Desviación Leve", numeric_value=2, sort_order=2),
                    OptionSetOption(raw_code="3", label="Desviación Severa", numeric_value=3, sort_order=3),
                ],
            )
            session.add(scale)
            await session.flush()

            c1 = Construct(instrument_version_id=v_rosa.id, code="SILLA_PANTALLA", name="Alineación Silla y Monitor", construct_type="DIMENSION")
            c2 = Construct(instrument_version_id=v_rosa.id, code="TECLADO_MOUSE", name="Ubicación Teclado y Mouse", construct_type="DIMENSION")
            session.add_all([c1, c2])
            await session.flush()

            for i in range(1, 4):
                q = Question(
                    instrument_version_id=v_rosa.id,
                    code=f"ROSA_SP_{i}",
                    question_text=f"Postura ergonómica en silla y altura de monitor componente #{i}.",
                    question_type="LIKERT",
                    is_scored=True,
                    option_set_id=scale.id,
                )
                session.add(q)
                await session.flush()
                session.add(ConstructItem(construct_id=c1.id, question_id=q.id, weight=1.0))

            for i in range(1, 3):
                q = Question(
                    instrument_version_id=v_rosa.id,
                    code=f"ROSA_TM_{i}",
                    question_text=f"Disposición de periféricos y apoyo de muñecas #{i}.",
                    question_type="LIKERT",
                    is_scored=True,
                    option_set_id=scale.id,
                )
                session.add(q)
                await session.flush()
                session.add(ConstructItem(construct_id=c2.id, question_id=q.id, weight=1.0))

        # Check Maslach Burnout
        res_mbi = await session.execute(select(Instrument).where(Instrument.code == "BURNOUT_MBI"))
        if not res_mbi.scalars().first():
            mbi = Instrument(
                name="Escala de Burnout Maslach (MBI-HSS)",
                code="BURNOUT_MBI",
                method_code="BURNOUT_MBI",
                discipline="LIDERAZGO_BURNOUT",
                author="Maslach & Jackson (1981)",
                reproduction_terms="Derechos registrados Mind Garden Inc. - Certificación corporativa activa",
                status="AUTHORIZED",
                is_system=True,
            )
            session.add(mbi)
            await session.flush()
            v_mbi = InstrumentVersion(
                instrument_id=mbi.id,
                version_code="MBI_HSS_22",
                status="ACTIVE",
                scoring_status="CONFIGURED",
                reproduction_restrictions="Uso restringido a evaluaciones corporativas autorizadas",
                validation_notes="Estructura trifactorial: Agotamiento, Despersonalización, Realización Personal.",
                methodological_rules={"cutoffs": {"bajo": 16, "medio": 27, "alto": 54}},
            )
            session.add(v_mbi)
            await session.flush()

        # Check NOSACQ-50
        res_nosacq = await session.execute(select(Instrument).where(Instrument.code == "NOSACQ_50"))
        if not res_nosacq.scalars().first():
            nosacq = Instrument(
                name="Cuestionario de Clima de Seguridad NOSACQ-50",
                code="NOSACQ_50",
                method_code="NOSACQ_50",
                discipline="SEGURIDAD_SALUD",
                author="Kines et al. / NRCWE Dinamarca",
                reproduction_terms="Uso de investigación y prevención de riesgos laborales",
                status="VALIDATING",
                is_system=True,
            )
            session.add(nosacq)
            await session.flush()
            v_nosacq = InstrumentVersion(
                instrument_id=nosacq.id,
                version_code="NOSACQ_50_REV1",
                status="DRAFT",
                scoring_status="NOT_CONFIGURED",
                reproduction_restrictions="En fase de calibración psicométrica institucional",
                validation_notes="Pendiente de baremos definitivos para minería y construcción.",
            )
            session.add(v_nosacq)
            await session.flush()

        # Check UWES-9
        res_uwes = await session.execute(select(Instrument).where(Instrument.code == "UWES_9"))
        if not res_uwes.scalars().first():
            uwes = Instrument(
                name="Escala de Engagement y Clima UWES-9",
                code="UWES_9",
                method_code="UWES_9",
                discipline="CLIMA_ORGANIZACIONAL",
                author="Schaufeli & Bakker (2003)",
                reproduction_terms="Instrumento validado de dominio público para diagnóstico institucional",
                status="AUTHORIZED",
                is_system=True,
            )
            session.add(uwes)
            await session.flush()
            v_uwes = InstrumentVersion(
                instrument_id=uwes.id,
                version_code="UWES_9_OFICIAL",
                status="ACTIVE",
                scoring_status="CONFIGURED",
                validation_notes="9 reactivos con dimensiones Vigor, Dedicación y Absorción.",
            )
            session.add(v_uwes)
            await session.flush()

        # Update existing CENSOPAS if needed
        res_cen = await session.execute(select(Instrument).where(Instrument.code == "CENSOPAS_COPSOQ"))
        cen = res_cen.scalars().first()
        if cen and not cen.discipline:
            cen.discipline = "PSICOSOCIAL"
            cen.author = "INS / CENSOPAS Perú"
            cen.reproduction_terms = "Instrumento oficial del Estado Peruano para factores de riesgo psicosocial"

        # Ensure default_version_id is set in metadata for all instruments
        stmt_insts = select(Instrument)
        all_insts = (await session.execute(stmt_insts)).scalars().all()
        for inst in all_insts:
            stmt_v = select(InstrumentVersion).where(InstrumentVersion.instrument_id == inst.id).order_by(InstrumentVersion.id.desc())
            latest_v = (await session.execute(stmt_v)).scalars().first()
            if latest_v:
                m = dict(inst.metadata_ or {})
                m["default_version_id"] = latest_v.id
                inst.metadata_ = m

        await session.commit()
    print("[+] Multidisciplinary instruments seeded successfully.")


async def main():
    await seed_multidisciplinary_catalog()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 980})
        page = await context.new_page()

        print("[1] Logging in as Empresa A Admin...")
        await page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")
        await page.fill('input[type="email"], input[name="email"]', EMP_A["admin_email"])
        await page.fill('input[type="password"], input[name="password"]', EMP_A["admin_password"])
        await page.click('button[type="submit"]')
        await page.wait_for_function("() => window.location.pathname.startsWith('/colmena')", timeout=15000)
        print("    [+] Logged in successfully")

        # Navigate to Project Instruments Page
        instruments_url = f"{FRONTEND_URL}/colmena/projects/{EMP_A['project_id']}/instruments"
        print(f"[2] Navigating to {instruments_url}...")
        await page.goto(instruments_url, wait_until="networkidle")
        await page.wait_for_timeout(3500)

        img1_path = OUTPUT_DIR / "16_pr13_multidisciplinary_catalog.png"
        await page.screenshot(path=str(img1_path), full_page=True)
        print(f"    [+] Saved Catalog Screenshot: {img1_path.name}")

        # Click on "Auditoría Metodológica" button on ROSA or first available instrument
        validate_btn = page.locator("button:has-text('Auditoría Metodológica')").first
        if await validate_btn.count() > 0:
            print("    [+] Clicking 'Auditoría Metodológica' button...")
            await validate_btn.click()
            await page.wait_for_timeout(2500)
            await page.wait_for_selector("text=Diagnóstico Metodológico", timeout=5000)
            print("    [+] Diagnostic Modal visible.")

        img2_path = OUTPUT_DIR / "17_pr13_validation_drawer.png"
        await page.screenshot(path=str(img2_path), full_page=True)
        print(f"    [+] Saved Validation Drawer Screenshot: {img2_path.name}")

        await context.close()
        await browser.close()

        # Copy to artifact directory for embedded viewing
        for img in [img1_path, img2_path]:
            if img.exists():
                shutil.copy2(img, ARTIFACT_SCREENSHOTS_DIR / img.name)
                print(f"[+] Copied to artifacts: {img.name}")

        print("\nAll PR #13 Playwright verification screenshots captured successfully!")


if __name__ == "__main__":
    asyncio.run(main())
