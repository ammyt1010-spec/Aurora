"""ReportService (harness §39).

Ensambla un *bundle* (estudio + resultados de análisis ya persistidos +
resultados CENSOPAS con privacidad aplicada + `barem_results`/baremación) y
lo renderiza al formato pedido:
  - DOCX (default): Word con ficha técnica, tabla de baremación por
    dimensión y gráficas embebidas (`report_docx.py`).
  - JSON: el mismo bundle sin renderizar, para integraciones.
No se recalcula estadística durante la generación, sólo se ensamblan
resultados ya persistidos (`responses -> analysis_run -> analysis_results ->
report_run`, harness).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.action_plan_status import compute_effective_status
from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.services.billing_service import BillingService
from app.models.analysis import AnalysisResult, AnalysisRun
from app.models.bsc import ActionPlan, ActionPlanItem, Kpi
from app.models.censopas import Barem
from app.models.construct import Construct
from app.models.project import Project
from app.models.user import Organization, User
from app.repositories.analytics import AnalyticsRepository
from app.repositories.reports import ReportRepository
from app.repositories.studies import StudyRepository
from app.schemas.reports import ReportRunCreate, ReportTemplateCreate
from app.services.censopas_methodology import (
    resolve_censopas_methodological_status,
    resolve_official_equivalence_enabled,
)
from app.services.censopas_service import CensopasScoringService
from app.services.response_descriptive_service import ResponseDescriptiveService
from app.services.scoring_service import ScoringService
from app.services.telemetry_service import TelemetryService

# Fase 4: separar D1-D6 de S1-S20 en cualquier consumidor del bundle —
# nunca filtrar por posición en la lista, siempre por `construct_type` real.
_DIMENSION_TYPE = "DIMENSION"
_SUBDIMENSION_TYPE = "SUBDIMENSION"

_CONFIDENTIALITY_NOTICE = (
    "Documento de uso interno del Comité/Grupo de Trabajo de Seguridad y Salud en el "
    "Trabajo. Contiene resultados colectivos únicamente — no incluye identificadores "
    "de participantes ni registros individuales."
)


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ReportRepository(session)
        self.study_repo = StudyRepository(session)
        self.analytics_repo = AnalyticsRepository(session)

    async def create_template(self, payload: ReportTemplateCreate):
        from app.models.report import ReportTemplate

        template = ReportTemplate(
            code=payload.code,
            name=payload.name,
            report_type=payload.report_type,
            instrument_version_id=payload.instrument_version_id,
            template_config=payload.template_config,
        )
        template = await self.repo.add_template(template)
        await self.session.commit()
        return template

    async def get_run(self, run_id: int):
        run = await self.repo.get_run(run_id)
        if run is None:
            raise NotFoundError(f"Reporte {run_id} no encontrado")
        return run

    async def generate(self, study_id: int, payload: ReportRunCreate):
        from app.models.report import ReportRun

        study = await self.study_repo.get(study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")

        # In production a report, including its preview, consumes exactly
        # one paid company order. No tariff is pre-filled before approval.
        billing = BillingService(self.session)
        paid_order = await billing.reserve_report_order(payload.billing_order_id, study_id)

        if payload.analysis_run_id is not None:
            analysis = await self.session.get(AnalysisRun, payload.analysis_run_id)
            if analysis is None or analysis.study_id != study_id:
                raise NotFoundError("El análisis seleccionado no pertenece a este estudio")

        report_run = ReportRun(
            billing_order_id=paid_order.id if paid_order else None,
            study_id=study_id,
            report_template_id=payload.report_template_id,
            analysis_run_id=payload.analysis_run_id,
            requested_by_user_id=payload.requested_by_user_id,
            output_format=payload.output_format,
            status="PENDING",
            metadata_={
                "report_mode": payload.report_mode,
                "sections": payload.sections,
            },
        )
        report_run = await self.repo.add_run(report_run)
        await self.session.flush()

        try:
            bundle = await self._build_bundle(
                study,
                payload.analysis_run_id,
                report_mode=payload.report_mode,
                sections=payload.sections,
                report_run=report_run,
            )

            storage_dir = Path(get_settings().export_storage_dir).parent / "reports_storage"
            storage_dir.mkdir(parents=True, exist_ok=True)

            if payload.output_format == "DOCX":
                from app.services.report_docx import render_report_docx

                file_bytes = render_report_docx(bundle)
                path = storage_dir / f"{report_run.public_id}.docx"
                path.write_bytes(file_bytes)
            elif payload.output_format == "PDF":
                # El PDF nunca se renderiza aparte: siempre es una conversión
                # del mismo DOCX (LibreOffice headless), para que el layout
                # entregado en PDF y en Word coincida por construcción.
                from app.services.report_docx import render_report_docx
                from app.services.report_pdf_convert import docx_to_pdf

                docx_bytes = render_report_docx(bundle)
                file_bytes = await docx_to_pdf(docx_bytes)
                path = storage_dir / f"{report_run.public_id}.pdf"
                path.write_bytes(file_bytes)
            else:
                file_bytes = json.dumps(bundle, indent=2, default=str, ensure_ascii=False).encode("utf-8")
                path = storage_dir / f"{report_run.public_id}.json"
                path.write_bytes(file_bytes)

            data_hash = hashlib.sha256(file_bytes).hexdigest()
            report_run.storage_path = str(path)
            report_run.data_hash = data_hash
            report_run.status = "COMPLETED"
            report_run.generated_at = datetime.now(UTC)
            await billing.consume_order(paid_order, report_run.id)
        except Exception as exc:
            # A failed render must not consume the paid authorization. Keep
            # the audit record of failure but release the single-use link.
            report_run.billing_order_id = None
            if paid_order is not None:
                paid_order.status = "PAID"
                paid_order.consumed_at = None
            report_run.status = "FAILED"
            report_run.error_message = str(exc)
            await self.session.commit()
            raise

        await self.session.commit()
        await self.session.refresh(report_run)
        return report_run

    async def generate_preview(self, study_id: int, payload: ReportRunCreate) -> tuple:
        """Genera el DOCX canónico (siempre, sin importar `output_format`
        pedido) y deriva su PDF de preview convirtiéndolo con LibreOffice.

        El PDF de preview se guarda como archivo hermano del `.docx`
        (`{public_id}.pdf`, mismo `report_run`) en vez de agregar una
        columna nueva a `ReportRun` — el path se puede derivar siempre por
        convención desde `storage_path`. `GET /reports/{id}/download` sigue
        sirviendo ese mismo `.docx` sin regenerar nada: es el archivo que
        efectivamente se descarga al exportar.
        """
        from app.services.report_pdf_convert import count_pdf_pages, docx_to_pdf

        forced_payload = payload.model_copy(update={"output_format": "DOCX"})
        report_run = await self.generate(study_id, forced_payload)

        docx_path = Path(report_run.storage_path)
        try:
            pdf_bytes = await docx_to_pdf(docx_path.read_bytes())
            pdf_path = docx_path.with_suffix(".pdf")
            pdf_path.write_bytes(pdf_bytes)
        except Exception as exc:
            # A failed preview does not consume a paid report: restore credit.
            from app.models.billing import ReportOrder
            if report_run.billing_order_id is not None:
                order = await self.session.get(ReportOrder, report_run.billing_order_id)
                if order is not None:
                    order.status = "PAID"
                    order.consumed_at = None
                report_run.billing_order_id = None
            report_run.status = "FAILED"
            report_run.error_message = f"Falló la conversión de vista previa: {exc}"
            await self.session.commit()
            raise
        return report_run, count_pdf_pages(pdf_bytes)

    async def _build_bundle(
        self,
        study,
        analysis_run_id: int | None,
        *,
        report_mode: str = "PROVISIONAL",
        sections: list[str] | None = None,
        report_run=None,
    ) -> dict:
        bundle: dict = {
            "study": {
                "id": study.id,
                "public_id": str(study.public_id),
                "code": f"EST-{study.id:06d}",
                "name": study.name,
                "study_type": study.study_type,
                "status": study.status,
                "period_start": study.start_at.isoformat() if study.start_at else None,
                "period_end": study.end_at.isoformat() if study.end_at else None,
                "instrument_name": study.instrument_name,
                "instrument_version_code": study.instrument_version_code,
            },
            "generated_at": datetime.now(UTC).isoformat(),
            "report_mode": report_mode,
            "sections": sections or [],
            "methodological_status": None,
            "methodological_label": None,
            "cover": None,
            "sociolaboral_profile": [],
            "dimension_results": [],
            "subdimension_results": [],
            "interpretation": [],
            "priority_ranking": [],
            "conclusions": [],
            "analysis_results": [],
            "censopas_results": [],
            "barem_results": None,
            "action_plans": [],
            "premium_analytics": None,
            "traceability": None,
            "data_quality": None,
            "executive_summary": None,
        }

        if analysis_run_id is not None:
            run = await self.analytics_repo.get_run(analysis_run_id)
            if run is not None:
                bundle["analysis_results"] = [self._serialize_result(r) for r in run.results]
        else:
            stmt = (
                select(AnalysisResult)
                .join(AnalysisRun, AnalysisResult.analysis_run_id == AnalysisRun.id)
                .where(AnalysisRun.study_id == study.id)
                .order_by(AnalysisResult.created_at.desc())
                .limit(50)
            )
            results = list((await self.session.execute(stmt)).scalars().all())
            bundle["analysis_results"] = [self._serialize_result(r) for r in results]

        censopas_service = CensopasScoringService(self.session)
        construct_results = await censopas_service.get_results(study.id)
        official_equivalence_enabled = await resolve_official_equivalence_enabled(
            censopas_service.instrument_repo, study.instrument_version_id
        )
        barem = await censopas_service.repo.get_barem(study.barem_id) if study.barem_id else None
        # Fase 1/7 (harness §31): única autoridad para "oficial"/"referencia" —
        # nunca inferir localmente, siempre censopas_methodology.py.
        bundle["methodological_label"] = resolve_censopas_methodological_status(
            barem, official_equivalence_enabled
        )
        censopas_payload = [
            censopas_service.apply_privacy(
                r,
                study.min_publishable_n,
                barem=barem,
                official_equivalence_enabled=official_equivalence_enabled,
            )
            for r in construct_results
        ]
        bundle["censopas_results"] = censopas_service.attach_priority_ranks(censopas_payload)

        telemetry = await TelemetryService(self.session).get_study_telemetry(study.id)
        bundle["data_quality"] = telemetry.model_dump(mode="json")
        bundle["executive_summary"] = self._build_executive_summary(
            bundle["censopas_results"], bundle["data_quality"], bundle["methodological_label"]
        )

        if study.instrument_version_id is not None:
            readiness = await censopas_service.get_readiness(study.instrument_version_id)
            bundle["methodological_status"] = readiness
            if report_mode == "OFFICIAL" and not readiness["ready_for_official_reporting"]:
                raise ConflictError(
                    "El reporte oficial está bloqueado porque la versión CENSOPAS no cumple readiness.",
                    readiness=readiness,
                )
            overview = await ScoringService(self.session).get_overview(study.id)
            bundle["barem_results"] = overview.model_dump(mode="json")

        # Fase 4/5: D1-D6 y S1-S20 se construyen desde `censopas_results`
        # (trichotomy favorable/intermedio/desfavorable + clasificación
        # colectiva + priority_rank ya agrupado por construct_type en
        # `attach_priority_ranks`) — es la MISMA fuente que ya usaba el PDF,
        # y la que trae exactamente los campos que pide la tabla CENSOPAS
        # (antes el DOCX usaba `barem_results`, una fuente distinta con
        # bandas/media/mediana pero sin trichotomy — esa divergencia era
        # el origen de GAP-REPORT-PDF-PARITY). `barem_results` se conserva
        # en el bundle para compatibilidad JSON (media/mediana), pero deja
        # de ser la fuente de las secciones D1-D6/S1-S20/interpretación.
        bundle["dimension_results"] = [
            r for r in bundle["censopas_results"] if r.get("construct_type") == _DIMENSION_TYPE
        ]
        bundle["subdimension_results"] = [
            r for r in bundle["censopas_results"] if r.get("construct_type") == _SUBDIMENSION_TYPE
        ]

        bundle["sociolaboral_profile"] = await self._build_sociolaboral_profile(study)
        bundle["action_plans"] = await self._build_action_plans(study.id)
        bundle["priority_ranking"] = self._build_priority_ranking(bundle["dimension_results"])
        bundle["interpretation"] = self._build_interpretation(
            bundle["dimension_results"], bundle["action_plans"]
        )
        bundle["premium_analytics"] = self._build_premium_analytics(
            bundle["analysis_results"], study.min_publishable_n
        )
        bundle["cover"] = await self._build_cover(study, bundle, report_run)
        bundle["traceability"] = await self._build_traceability(
            study, bundle, report_run, analysis_run_id
        )
        bundle["conclusions"] = self._build_conclusions(bundle)
        return bundle

    async def _build_cover(self, study, bundle: dict, report_run) -> dict:
        organization_name = None
        project = await self.session.get(Project, study.project_id)
        if project is not None and project.organization_id is not None:
            organization = await self.session.get(Organization, project.organization_id)
            organization_name = organization.name if organization else None

        evaluator_label = None
        requested_by_user_id = getattr(report_run, "requested_by_user_id", None)
        if requested_by_user_id is not None:
            user = await self.session.get(User, requested_by_user_id)
            if user is not None:
                full_name = " ".join(filter(None, (user.first_name, user.last_name))).strip()
                evaluator_label = full_name or user.username or user.email

        readiness = bundle.get("methodological_status") or {}
        return {
            "organization_name": organization_name,
            "study_code": bundle["study"]["code"],
            "period_start": bundle["study"]["period_start"],
            "period_end": bundle["study"]["period_end"],
            "instrument_label": "CENSOPAS-COPSOQ",
            "version_kind": readiness.get("version_kind", "UNKNOWN"),
            "generated_at": bundle["generated_at"],
            "evaluator_label": evaluator_label,
            "confidentiality_notice": _CONFIDENTIALITY_NOTICE,
            "methodological_label": bundle["methodological_label"],
        }

    async def _build_sociolaboral_profile(self, study) -> list[dict]:
        """Fase 3: perfil sociolaboral (11 variables C-001..C-011, EXOGENOUS,
        nunca puntuables — harness §9). Reusa `ResponseDescriptiveService`
        (misma fuente que Resultados) y aplica supresión n<min_publishable_n
        por categoría aquí mismo, porque ese servicio no suprime por diseño
        (sirve también a vistas internas con otro umbral de exposición)."""
        try:
            descriptives = await ResponseDescriptiveService(self.session).get(study.id)
        except NotFoundError:
            return []

        profile = []
        for question in descriptives.questions:
            if question.research_role != "EXOGENOUS" or question.is_scored:
                continue
            categories = []
            for frequency in question.frequencies:
                suppressed = frequency.n < descriptives.min_publishable_n
                categories.append(
                    {
                        "label": frequency.label,
                        "n": None if suppressed else frequency.n,
                        "percentage": None if suppressed else frequency.percentage,
                        "suppressed": suppressed,
                    }
                )
            profile.append(
                {
                    "code": question.code,
                    "label": question.short_label or question.question_text,
                    "valid_n": question.valid_n,
                    "missing_n": question.missing_n,
                    "categories": categories,
                }
            )
        return profile

    @staticmethod
    def _build_priority_ranking(dimension_results: list[dict]) -> list[dict]:
        """Fase 7: reusa `priority_rank`/`unfavorable_pct` ya calculados por
        `CensopasScoringService.attach_priority_ranks` — no reordena con una
        regla nueva. El orden es una ayuda de priorización preventiva, nunca
        una clasificación oficial adicional (se deja explícito en el render)."""
        ranked = sorted(
            (r for r in dimension_results if not r.get("suppressed")),
            key=lambda r: (r.get("priority_rank") if r.get("priority_rank") is not None else 9999),
        )
        return [
            {
                "construct_code": r.get("construct_code"),
                "construct_name": r.get("construct_name"),
                "priority_rank": r.get("priority_rank"),
                "n_valid": r.get("n_valid"),
                "unfavorable_pct": r.get("unfavorable_pct"),
                "collective_classification": r.get("collective_classification"),
            }
            for r in ranked
        ]

    @staticmethod
    def _build_interpretation(dimension_results: list[dict], action_plans: list[dict]) -> list[dict]:
        """Fase 6: separa hallazgo / clasificación / prioridad / hipótesis a
        contrastar / orientación preventiva / limitación — nunca causalidad,
        nunca diagnóstico individual. La hipótesis y la orientación vienen de
        `ActionPlanItem.origin_hypothesis`/`action_description` cuando existe
        una acción vinculada al mismo constructo; si no hay acción registrada
        se deja constancia explícita de que aún no se contrastó."""
        hypotheses_by_construct: dict[str, list[str]] = {}
        actions_by_construct: dict[str, list[str]] = {}
        for plan in action_plans:
            for item in plan.get("items") or []:
                code = item.get("construct_code")
                if not code:
                    continue
                if item.get("origin_hypothesis"):
                    hypotheses_by_construct.setdefault(code, []).append(item["origin_hypothesis"])
                if item.get("action_description"):
                    actions_by_construct.setdefault(code, []).append(item["action_description"])

        entries = []
        for result in dimension_results:
            code = result.get("construct_code")
            name = result.get("construct_name") or code or "—"
            if result.get("suppressed"):
                entries.append(
                    {
                        "construct_code": code,
                        "construct_name": name,
                        "finding": "Resultado suprimido por privacidad (n por debajo del mínimo publicable).",
                        "classification": None,
                        "priority_rank": None,
                        "origin_hypothesis": [],
                        "preventive_orientation": [],
                        "limitation": "No es posible interpretar un resultado suprimido sin exponer el grupo.",
                    }
                )
                continue
            classification = result.get("collective_classification")
            entries.append(
                {
                    "construct_code": code,
                    "construct_name": name,
                    "finding": (
                        f"Se observó una distribución colectiva en {name} "
                        f"(n={result.get('n_valid', '—')})."
                    ),
                    "classification": classification,
                    "priority_rank": result.get("priority_rank"),
                    "origin_hypothesis": hypotheses_by_construct.get(code, []),
                    "preventive_orientation": actions_by_construct.get(code, [])
                    or [
                        "El Grupo de Trabajo deberá contrastar hipótesis de origen y definir "
                        "medidas preventivas para esta dimensión."
                    ],
                    "limitation": (
                        "El resultado describe una exposición colectiva; no permite diagnóstico "
                        "individual. La hipótesis de origen es algo a contrastar, no una causa "
                        "demostrada."
                    ),
                }
            )
        return entries

    def _build_conclusions(self, bundle: dict) -> list[str]:
        """Fase 9: solo texto derivado de datos ya calculados en el bundle —
        ningún resultado concreto queda hardcodeado, se lee de
        `executive_summary`/`dimension_results`/`methodological_label`."""
        conclusions: list[str] = []
        summary = bundle.get("executive_summary") or {}
        priority_dimensions = summary.get("priority_dimensions") or []
        if priority_dimensions:
            names = ", ".join(
                d.get("construct_name") or d.get("construct_code") or "—"
                for d in priority_dimensions
            )
            conclusions.append(f"Las dimensiones prioritarias para intervención preventiva fueron: {names}.")
        else:
            conclusions.append(
                "No se identificaron dimensiones con prioridad de intervención alta en esta medición."
            )

        protective = [
            r
            for r in bundle.get("dimension_results") or []
            if not r.get("suppressed")
            and r.get("collective_classification") == "FACTOR_PROTECTOR"
        ]
        if protective:
            names = ", ".join(r.get("construct_name") or r.get("construct_code") or "—" for r in protective)
            conclusions.append(f"Se identificaron factores protectores en: {names}.")
        else:
            conclusions.append("No se identificaron factores protectores destacados en esta medición.")

        conclusions.append(
            "Los resultados son de carácter colectivo — describen a un grupo de trabajadores, "
            "no a personas individuales, y no constituyen diagnóstico clínico."
        )

        label = bundle.get("methodological_label") or {}
        barem = (bundle.get("traceability") or {}).get("barem") or {}
        if not label.get("official_equivalence"):
            conclusions.append(
                "Resultado basado en baremo de referencia. No equivalente al resultado oficial "
                "CENSOPAS-COPSOQ."
            )
        conclusions.append(
            "Se recomienda conservar la versión del instrumento"
            + (f" ({bundle['study'].get('instrument_version_code')})" if bundle.get("study", {}).get("instrument_version_code") else "")
            + " y el baremo aplicado"
            + (f" ({barem.get('name')} · versión {barem.get('version')})" if barem.get("name") else "")
            + " para permitir comparaciones futuras."
        )
        return conclusions

    async def _build_action_plans(self, study_id: int) -> list[dict]:
        stmt = (
            select(ActionPlan)
            .where(ActionPlan.study_id == study_id)
            .options(
                selectinload(ActionPlan.items)
                .selectinload(ActionPlanItem.kpis)
                .selectinload(Kpi.measurements)
            )
            .order_by(ActionPlan.created_at, ActionPlan.id)
        )
        plans = list((await self.session.execute(stmt)).scalars().all())
        construct_ids = {
            item.construct_id
            for plan in plans
            for item in plan.items
            if item.construct_id is not None
        }
        constructs = {}
        if construct_ids:
            construct_stmt = select(Construct).where(Construct.id.in_(construct_ids))
            constructs = {
                construct.id: construct
                for construct in (await self.session.execute(construct_stmt)).scalars().all()
            }
        payload = []
        for plan in plans:
            items = []
            for item in sorted(
                plan.items,
                key=lambda value: (
                    value.priority is None,
                    value.priority or 0,
                    value.id,
                ),
            ):
                construct = constructs.get(item.construct_id)
                kpis = []
                for kpi in sorted(item.kpis, key=lambda value: (value.code or "", value.id)):
                    measurements = sorted(
                        kpi.measurements, key=lambda value: value.measured_at
                    )
                    latest = measurements[-1] if measurements else None
                    kpis.append(
                        {
                            "code": kpi.code,
                            "name": kpi.name,
                            "description": kpi.description,
                            "formula": kpi.formula,
                            "unit": kpi.unit,
                            "baseline_value": float(kpi.baseline_value)
                            if kpi.baseline_value is not None
                            else None,
                            "target_value": float(kpi.target_value)
                            if kpi.target_value is not None
                            else None,
                            "frequency": kpi.frequency,
                            "status": kpi.status,
                            "latest_measurement": (
                                {
                                    "measured_at": latest.measured_at.isoformat(),
                                    "numeric_value": float(latest.numeric_value)
                                    if latest.numeric_value is not None
                                    else None,
                                    "text_value": latest.text_value,
                                    "status": latest.status,
                                    "source_reference": latest.source_reference,
                                }
                                if latest
                                else None
                            ),
                            "current_value": (
                                float(latest.numeric_value)
                                if latest and latest.numeric_value is not None
                                else None
                            ),
                        }
                    )
                items.append(
                    {
                        "construct_code": construct.code if construct else None,
                        "construct_name": construct.name if construct else None,
                        "analysis_run_id": item.analysis_run_id,
                        "title": item.title,
                        "finding": item.finding,
                        "origin_hypothesis": item.origin_hypothesis,
                        "action_description": item.action_description,
                        "responsible_label": item.responsible_label,
                        "priority": item.priority,
                        "due_date": item.due_date.isoformat() if item.due_date else None,
                        "status": item.status,
                        "effective_status": compute_effective_status(item.status, item.due_date),
                        "kpis": kpis,
                    }
                )
            payload.append(
                {
                    "name": plan.name,
                    "status": plan.status,
                    "approved": plan.approved_at is not None,
                    "approved_at": plan.approved_at.isoformat()
                    if plan.approved_at
                    else None,
                    "items": items,
                }
            )
        return payload


    
    @staticmethod
    def _build_executive_summary(
        censopas_results: list[dict],
        data_quality: dict | None,
        methodological_label: dict | None = None,
    ) -> dict:
        """Guía y modelos de reporte §31: primer contenido sustantivo del
        informe — participación, niveles principales, prioridades. Se deriva
        de `censopas_results` (ya con privacidad aplicada) y `data_quality`;
        no ejecuta cálculo nuevo."""
        publishable = [
            result
            for result in censopas_results
            if not result.get("suppressed") and result.get("unfavorable_pct") is not None
        ]
        ranked = sorted(publishable, key=lambda result: result["unfavorable_pct"], reverse=True)
        high_risk_count = sum(
            1 for result in ranked if result.get("collective_classification") == "RIESGO_ALTO"
        )
        if ranked:
            headline = (
                f"{high_risk_count} de {len(ranked)} dimensiones en riesgo alto (≥50% desfavorable)."
                if high_risk_count
                else "Ninguna dimensión alcanza el umbral de riesgo alto (≥50% desfavorable)."
            )
        else:
            headline = "Todavía no hay dimensiones con resultados publicables para este estudio."

        return {
            "n_valid": (data_quality or {}).get("valid_count"),
            "completion_rate": (data_quality or {}).get("completion_rate"),
            "headline": headline,
            "barem_status": (methodological_label or {}).get("barem_status"),
            "official_equivalence": (methodological_label or {}).get("official_equivalence"),
            "priority_dimensions": [
                {
                    "construct_code": result.get("construct_code"),
                    "construct_name": result.get("construct_name"),
                    "unfavorable_pct": result.get("unfavorable_pct"),
                    "classification": result.get("collective_classification"),
                }
                for result in ranked[:3]
            ],
        }

    @staticmethod
    def _build_premium_analytics(
        analysis_results: list[dict], min_publishable_n: int
    ) -> dict:
        premium_types = {
            "SPEARMAN",
            "CHI_SQUARE",
            "MANN_WHITNEY",
            "KRUSKAL_WALLIS",
            "NORMALITY",
            "LOGISTIC_REGRESSION",
            "KMEANS",
            "CRONBACH_ALPHA",
            "MCDONALD_OMEGA",
        }
        results = [
            result
            for result in analysis_results
            if result.get("result_type") in premium_types
            and (
                result.get("n_valid") is None
                or result["n_valid"] >= min_publishable_n
            )
        ]
        significant = [
            result
            for result in results
            if (
                result.get("adjusted_p_value")
                if result.get("adjusted_p_value") is not None
                else result.get("p_value")
            )
            is not None
            and (
                result.get("adjusted_p_value")
                if result.get("adjusted_p_value") is not None
                else result.get("p_value")
            )
            < 0.05
        ]
        return {
            "status": "AVAILABLE" if results else "NO_RESULTS",
            "methods": sorted({result["result_type"] for result in results}),
            "result_count": len(results),
            "significant_result_count": len(significant),
            "privacy": {
                "minimum_n": min_publishable_n,
                "individual_assignments_removed": True,
                "small_group_results_removed": True,
            },
            "limitations": [
                "Los resultados premium complementan y no modifican el semáforo CENSOPAS.",
                "Las asociaciones no demuestran causalidad.",
                "K-means es exploratorio y no publica asignaciones individuales.",
                "La regresión no debe utilizarse para decisiones laborales individuales.",
            ],
            "results": results[:100],
        }

    async def _build_traceability(
        self, study, bundle: dict, report_run=None, requested_analysis_run_id: int | None = None
    ) -> dict:
        runs_stmt = (
            select(AnalysisRun)
            .where(AnalysisRun.study_id == study.id)
            .order_by(AnalysisRun.created_at, AnalysisRun.id)
        )
        runs = list((await self.session.execute(runs_stmt)).scalars().all())
        barem_payload = None
        if study.barem_id is not None:
            barem = await self.session.get(Barem, study.barem_id)
            if barem is not None:
                barem_payload = {
                    "id": barem.id,
                    "name": barem.name,
                    "version": barem.barem_version,
                    "type": barem.metadata_.get("barem_type"),
                    "source_reference": barem.source_reference,
                    "content_hash": barem.metadata_.get("content_hash"),
                    "status": barem.status,
                }
        readiness = bundle.get("methodological_status") or {}
        methodological_label = bundle.get("methodological_label") or {}
        data_quality = bundle.get("data_quality") or {}
        return {
            "report_run_id": getattr(report_run, "id", None),
            "report_run_public_id": (
                str(report_run.public_id) if getattr(report_run, "public_id", None) else None
            ),
            "study_id": study.id,
            "study_code": bundle.get("study", {}).get("code"),
            "analysis_run_id": requested_analysis_run_id,
            "lineage": [
                "responses.raw_code",
                "response_scores.risk_value",
                "response_scores.score_0_100",
                "construct_scores.score_0_100",
                "construct_results",
                "report_run",
            ],
            "instrument_version_id": study.instrument_version_id,
            "version_kind": readiness.get("version_kind"),
            "manifest_hash": (
                readiness.get("manifest_hash")
                or (getattr(study.instrument_version, "config", {}) or {}).get(
                    "manifest_hash"
                )
            ),
            "barem": barem_payload,
            "official_equivalence": methodological_label.get("official_equivalence"),
            "exclusions": {
                "excluded_count": data_quality.get("excluded_count"),
                "abandoned_count": data_quality.get("abandoned_count"),
                "review_count": data_quality.get("review_count"),
                "criteria": (
                    "Sesiones sin estado COMPLETED/validation_status=VALID quedan fuera de "
                    "`n_valid`; el detalle agregado está en Calidad de datos."
                ),
            },
            "analysis_runs": [
                {
                    "analysis_type": run.analysis_type,
                    "status": run.status,
                    "engine": run.engine,
                    "engine_version": run.engine_version,
                    "algorithm_version": run.algorithm_version,
                    "input_hash": run.input_hash,
                    "completed_at": run.completed_at.isoformat()
                    if run.completed_at
                    else None,
                }
                for run in runs
            ],
            "privacy": {
                "min_publishable_n": study.min_publishable_n,
                "individual_records_included": False,
                "secondary_suppression": True,
            },
            "report": {
                "mode": bundle.get("report_mode"),
                "sections": bundle.get("sections"),
                "generated_at": bundle.get("generated_at"),
            },
        }

    # E-09: ningún reporte descargable debe exponer datos punto-a-punto,
    # aunque en el futuro algún otro tipo de análisis los incluya en
    # result_data — defensa en profundidad, independiente del control de rol
    # aplicado al generar el resultado.
    _INDIVIDUAL_LEVEL_KEYS = frozenset(
        {
            "points",
            "points_binned",
            "labels",
            "assignments",
            "predictions",
            "probabilities",
            "session_ids",
            "response_session_ids",
            "anonymous_tokens",
            "tokens",
            "row_ids",
        }
    )


    
    @classmethod
    def _sanitize_result_data(cls, value):
        """Retira identificadores y vectores fila-a-fila en cualquier profundidad."""
        if isinstance(value, dict):
            sanitized = {}
            for key, nested_value in value.items():
                normalized = str(key).lower()
                if (
                    normalized in cls._INDIVIDUAL_LEVEL_KEYS
                    or "session_id" in normalized
                    or "anonymous_token" in normalized
                ):
                    continue
                sanitized[key] = cls._sanitize_result_data(nested_value)
            return sanitized
        if isinstance(value, list):
            return [cls._sanitize_result_data(item) for item in value]
        return value

    @classmethod
    def _serialize_result(cls, result: AnalysisResult) -> dict:
        result_data = cls._sanitize_result_data(result.result_data or {})
        return {
            "result_type": result.result_type,
            "result_code": result.result_code,
            "n_valid": result.n_valid,
            "numeric_value": float(result.numeric_value) if result.numeric_value is not None else None,
            "statistic_value": float(result.statistic_value) if result.statistic_value is not None else None,
            "p_value": float(result.p_value) if result.p_value is not None else None,
            "adjusted_p_value": float(result.adjusted_p_value)
            if result.adjusted_p_value is not None
            else None,
            "effect_size": float(result.effect_size) if result.effect_size is not None else None,
            "effect_label": result.effect_label,
            "ci_lower": float(result.ci_lower) if result.ci_lower is not None else None,
            "ci_upper": float(result.ci_upper) if result.ci_upper is not None else None,
            "text_value": result.text_value,
            "result_data": result_data,
        }
