"""Seed del Estudio Modelo Aurora Pro: CENSOPAS-COPSOQ Versión Media (112 preguntas)
para el Sector Minero (Unidad Minera San Cristóbal / Compañía Minera Aurífera del Sur S.A.).

Genera una evaluación corporativa completa con:
  - 112 preguntas reales (3 sociodemográficas, 25 condiciones laborales mineras, 69 psicosociales, 15 salud/satisfacción).
  - 35 trabajadores mineros sintéticos (socavón, planta concentradora, mantenimiento, geología, campamento).
  - Baremos oficiales CENSOPAS con clasificación Verde, Amarillo, Rojo por dimensiones (D1-D6) y subdimensiones (S1-S20).
  - Pruebas inferenciales grupales por turnos (Día vs Noche) y áreas de trabajo.
  - Plan de Seguridad e Intervención Preventiva en Minería con acciones y KPIs.
  - Generación de informe ejecutivo en DOCX y PDF.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.models.audit import AuditLog
from app.models.bsc import ActionPlan, ActionPlanItem, Kpi
from app.models.censopas import Barem
from app.models.instrument import Instrument
from app.models.project import Project
from app.models.question import Question
from app.models.response import Response, ResponseSession, ResponseSessionUnit
from app.models.study import Study
from app.models.user import User, Organization
from app.schemas.projects import ProjectCreate
from app.schemas.reports import ReportRunCreate
from app.schemas.studies import StudyCreate, StudyUpdate
from app.schemas.surveys import SurveyFromInstrumentCreate
from app.services.censopas_service import CensopasScoringService
from app.services.instrument_service import InstrumentService
from app.services.project_service import ProjectService
from app.services.report_service import ReportService
from app.services.scoring_orchestrator import run_canonical_scoring
from app.services.study_service import StudyService
from app.services.survey_service import SurveyService

from scripts.seed_censopas_official import _load_seed_data, build_manifest
from scripts.seed_demo_current import import_reference_barem, load_question_options

OWNER_EMAIL = "demo@aurorapro.dev"
PROJECT_NAME = "Evaluación de Riesgos Psicosociales CENSOPAS Media - Unidad Minera San Cristóbal"
ORG_NAME = "Compañía Minera Aurífera del Sur S.A."

RNG = random.Random(20260921)

MINING_ROLES = [
  "Operador de Equipo Pesado",
  "Perforista Socavón",
  "Técnico Metalurgista Planta",
  "Supervisor de Seguridad SST",
  "Geólogo de Campo",
  "Mecánico de Mantenimiento",
  "Administrador de Campamento",
]

MINING_AREAS = [
  "Socavón / Mina Subterránea",
  "Planta Concentradora",
  "Mantenimiento Mecánico",
  "Geología y Exploraciones",
  "Administración y Campamento",
]

MINING_SHIFTS = ["Día (07:00 - 19:00)", "Noche (19:00 - 07:00)", "Rotativo 14x7"]


async def main():
  print("=== Sembrando Demostración Aurora Pro: Sector Minero (CENSOPAS Media 112 preguntas) ===")

  async with AsyncSessionLocal() as session:
    # 1. Obtener o crear usuario demo
    res = await session.execute(select(User).where(User.email == OWNER_EMAIL))
    user = res.scalars().first()
    if not user:
      res = await session.execute(select(User).order_by(User.id))
      user = res.scalars().first()

    if not user:
      user = User(email=OWNER_EMAIL, username="aurora_admin", first_name="Supervisor", status="ACTIVE")
      session.add(user)
      await session.commit()
      await session.refresh(user)

    print(f"[usuario] {user.email} (id={user.id})")

    # 2. Obtener o sembrar la versión MEDIUM-OFICIAL
    data = _load_seed_data()
    manifest = build_manifest(data, "MEDIUM", "CENSOPAS-MEDIA-MINERIA-V1")
    service = CensopasScoringService(session)

    res = await session.execute(
      select(Instrument).where(Instrument.code == "CENSOPAS_COPSOQ", Instrument.is_system.is_(True))
    )
    instrument = res.scalars().first()
    if not instrument:
      instrument = await InstrumentService(session).create_system_censopas_instrument()

    from app.models.instrument import InstrumentVersion
    from app.schemas.instruments import InstrumentVersionCreate

    res = await session.execute(
        select(InstrumentVersion).where(
            InstrumentVersion.instrument_id == instrument.id,
            InstrumentVersion.version_code == "MEDIUM-OFICIAL"
        )
    )
    version = res.scalars().first()
    if not version:
        inst_service = InstrumentService(session)
        version = await inst_service.create_version(
            instrument.id,
            InstrumentVersionCreate(
                version_code="MEDIUM-OFICIAL",
                version_name="Plan media — CENSOPAS-COPSOQ (oficial)",
                status="DRAFT",
            )
        )
        await service.import_manifest(version.id, manifest)
        await inst_service.update_version(version.id, payload=None, status="ACTIVE")
        await session.refresh(version)
    elif version.status == "DRAFT":
        await service.import_manifest(version.id, manifest)
        await InstrumentService(session).update_version(version.id, payload=None, status="ACTIVE")
        await session.refresh(version)

    print(f"[instrumento] CENSOPAS Media id={version.id} status={version.status}")

    # 3. Limpiar proyectos demo previos con el mismo nombre si existen
    res = await session.execute(
      select(Project).where(Project.owner_user_id == user.id, Project.name == PROJECT_NAME)
    )
    prev_project = res.scalars().first()
    if prev_project:
      print(f"[limpieza] Borrando proyecto anterior id={prev_project.id}")
      await session.execute(delete(AuditLog).where(AuditLog.project_id == prev_project.id))
      await session.execute(delete(Project).where(Project.id == prev_project.id))
      await session.commit()

    # 4. Obtener o crear Organización Minera
    org_res = await session.execute(select(Organization).where(Organization.name == ORG_NAME))
    org = org_res.scalars().first()

    project_payload = {
      "owner_user_id": user.id,
      "name": PROJECT_NAME,
      "project_type": "CENSO",
      "description": "Evaluación de Riesgos Psicosociales y Salud Ocupacional para 35 trabajadores en operaciones mineras de socavón y planta concentradora.",
    }
    if org:
      project_payload["organization_id"] = org.id
    else:
      project_payload["new_organization"] = {
        "name": ORG_NAME,
        "legal_name": ORG_NAME,
        "tax_id": "20481920194",
        "organization_type": "EMPRESA_PRIVADA",
      }

    project = await ProjectService(session).create(ProjectCreate(**project_payload))

    # 5. Generar Encuesta desde la Versión Media
    survey = await SurveyService(session).create_from_instrument(
      project.id,
      SurveyFromInstrumentCreate(
        created_by_user_id=user.id,
        instrument_version_id=version.id,
        name="Cuestionario CENSOPAS Media Minería",
      ),
    )

    # 6. Crear Baremo Oficial de Referencia
    barem = await import_reference_barem(session, version.id, "Baremo Minería Perú 2026")
    meta = dict(project.metadata_ or {})
    meta["barem_id"] = barem.id
    project.metadata_ = meta
    session.add(project)
    await session.commit()

    # 7. Crear Estudio Minero
    study = await StudyService(session).create(
      project.id,
      StudyCreate(
        survey_id=survey.id,
        name="Estudio Minero San Cristóbal 2026",
        study_type="CENSO",
        target_sample_size=35,
        min_publishable_n=5,
      ),
    )
    await StudyService(session).update(
      study.id, StudyUpdate(barem_id=barem.id, is_official_equivalence_enabled=True)
    )
    await StudyService(session).open(study.id)

    # 8. Cargar preguntas del cuestionario
    q_res = await session.execute(
      select(Question).where(Question.instrument_version_id == version.id)
    )
    questions = q_res.scalars().all()
    q_by_code = {q.code: q for q in questions}

    options_by_q = {}
    for q in questions:
      options_by_q[q.id] = await load_question_options(session, q.id)

    # 9. Crear 35 Sesiones de Respuesta Mineras
    print("[respuestas] Generando 35 respuestas mineras sintéticas...")
    for i in range(1, 36):
      role = RNG.choice(MINING_ROLES)
      area = RNG.choice(MINING_AREAS)
      shift = RNG.choice(MINING_SHIFTS)

      sess = ResponseSession(
        study_id=study.id,
        status="COMPLETED",
        validation_status="VALID",
        completed_at=datetime.now(UTC),
      )
      session.add(sess)
      await session.flush()

      # Respuestas a las 112 preguntas (incluyendo sociodemográficas y psicosociales)
      for q in questions:
        opts = options_by_q.get(q.id, [])
        if not opts:
          session.add(
            Response(
              study_id=study.id,
              response_session_id=sess.id,
              question_id=q.id,
              text_value=area if "área" in (q.question_text or "").lower() else role,
              raw_code=area if "área" in (q.question_text or "").lower() else role,
              is_missing=False,
            )
          )
          continue

        # Simular mayor tensión en socavón y turnos de noche
        if (
          "Socavón" in area
          or "Noche" in shift
        ) and q.code in ["C-012", "C-013", "C-014", "C-020", "C-025"]:
          selected_opt = opts[-1] if len(opts) > 1 else opts[0]
        else:
          selected_opt = RNG.choice(opts)

        session.add(
          Response(
            study_id=study.id,
            response_session_id=sess.id,
            question_id=q.id,
            option_id=selected_opt.id,
            raw_code=selected_opt.code,
            is_missing=False,
          )
        )

    await session.commit()

    # 10. Ejecutar Calificación Canónica CENSOPAS
    print("[scoring] Calculando puntuaciones y baremos...")
    run_obj, summary = await run_canonical_scoring(session, study.id)
    print(f"[scoring ok] AnalysisRun ID={run_obj.id}")

    # 11. Generar Plan de Seguridad Preventivo en Minería
    print("[plan] Creando Plan de Seguridad e Intervención Minera...")
    plan = ActionPlan(
      study_id=study.id,
      name="Plan de Prevención de Riesgos Psicosociales y Salud Ocupacional - Minería 2026",
      status="ACTIVE",
    )
    session.add(plan)
    await session.flush()

    item1 = ActionPlanItem(
      action_plan_id=plan.id,
      title="Programa de Control de Fatiga y Somnolencia en Turno Noche",
      finding="Elevada carga y exigencias psicológicas en operadores de maquinaria de socavón en turno nocturno.",
      origin_hypothesis="Extensión de jornadas de 12 horas en régimen atípico 14x7 con descansos intermedios limitados.",
      action_description="Implementar pausas activas obligatorias de 15 min cada 3 horas, evaluar somnolencia previa al turno y acondicionar salas de descanso térmico.",
      responsible_label="Superintendente de SST y Médico Ocupacional",
      priority=1,
      status="IN_PROGRESS",
    )
    item2 = ActionPlanItem(
      action_plan_id=plan.id,
      title="Protocolo de Apoyo Social y Conectividad en Campamento Minero",
      finding="Sentimiento de aislamiento familiar e interferencia del trabajo en la vida personal (Doble Presencia).",
      origin_hypothesis="Limitaciones en la conectividad digital y falta de actividades recreativas en campamento altoandino.",
      action_description="Ampliación de ancho de banda Wi-Fi en pabellones, torneos deportivos internos y servicio telefónico gratuito para contacto familiar.",
      responsible_label="Jefe de Bienestar Social y Recursos Humanos",
      priority=2,
      status="PENDING",
    )
    session.add_all([item1, item2])
    await session.commit()

    # 12. Generar Reporte Ejecutivo de Minería
    print("[reporte] Generando Informe Ejecutivo en PDF y DOCX...")
    rep_service = ReportService(session)
    report_run = await rep_service.generate(
      study.id, ReportRunCreate(output_format="DOCX", requested_by_user_id=user.id)
    )
    await rep_service.generate(
      study.id, ReportRunCreate(output_format="PDF", requested_by_user_id=user.id)
    )

    print(
      f"=== Sembrado Exitoso: Proyecto ID={project.id}, Estudio ID={study.id}, Reporte ID={report_run.id} ==="
    )


if __name__ == "__main__":
  asyncio.run(main())
