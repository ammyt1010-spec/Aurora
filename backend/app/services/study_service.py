from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationDomainError,
)
from app.core.pagination import Page, PageParams, paginate
from app.models.study import Study, StudySnapshot, StudyUnit, StudyUnitType
from app.models.censopas import Barem
from app.models.analytics_plan import AnalyticsPlan
from app.models.construct import Construct
from app.models.instrument import InstrumentVersion
from app.models.option_set import OptionSet
from app.models.project import Project
from app.models.question import Question
from app.models.scoring import ScoringRule
from app.models.survey import Survey, SurveyQuestion
from app.models.variable import Variable
from app.repositories.instruments import InstrumentRepository
from app.repositories.studies import StudyRepository
from app.repositories.surveys import SurveyRepository
from app.schemas.studies import (
    StudyCreate,
    StudyRead,
    StudyUnitCreate,
    StudyUnitTypeCreate,
    StudyUpdate,
)
from app.services.audit_service import AuditService

# Transiciones válidas de estudio (harness §15).
_ALLOWED_TRANSITIONS = {
    "DRAFT": "OPEN",
    "OPEN": "CLOSED",
    "CLOSED": "ARCHIVED",
}


class StudyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = StudyRepository(session)
        self.survey_repo = SurveyRepository(session)
        self.instrument_repo = InstrumentRepository(session)
        self.audit = AuditService(session)

    async def _validate_censopas_survey_completeness(
        self,
        survey: Survey,
        version: InstrumentVersion,
        study_version_id: int | None,
    ) -> None:
        """Require a CENSOPAS survey to preserve the exact version item set.

        Generic and intentionally partial surveys remain valid. CENSOPAS
        snapshots, however, must not silently omit scored or contextual items.
        """
        instrument = version.instrument
        if instrument is None or instrument.code != "CENSOPAS_COPSOQ":
            return
        if survey.instrument_version_id != version.id or study_version_id != version.id:
            raise ValidationDomainError(
                "El survey CENSOPAS debe estar vinculado a la misma versión del estudio."
            )

        expected_ids = set(
            (
                await self.session.execute(
                    select(Question.id).where(Question.instrument_version_id == version.id)
                )
            )
            .scalars()
            .all()
        )
        actual_ids = {link.question_id for link in survey.survey_questions}
        if not expected_ids:
            raise ValidationDomainError(
                "La versión CENSOPAS no tiene ítems y no puede abrirse como un survey completo."
            )

        missing_count = len(expected_ids - actual_ids)
        unexpected_count = len(actual_ids - expected_ids)
        if missing_count or unexpected_count:
            raise ValidationDomainError(
                "El survey CENSOPAS debe incluir exactamente los ítems de su versión; "
                f"faltan {missing_count} y hay {unexpected_count} que no pertenecen."
            )

    async def create(self, project_id: int, payload: StudyCreate) -> Study:
        survey = await self.survey_repo.get(payload.survey_id)
        if survey is None or survey.project_id != project_id:
            raise NotFoundError(f"Survey {payload.survey_id} no encontrado en este proyecto")

        project = await self.session.get(Project, project_id)
        if project is None:
            raise NotFoundError(f"Proyecto {project_id} no encontrado")
        # Enterprise projects can host independent instruments in one battery.
        # Only explicit non-CENSOPAS research campaigns avoid the project's
        # CENSOPAS barem; never apply that barem to a different instrument.
        is_censopas_campaign = project.project_type == "CENSO" and (
            payload.study_type != "RESEARCH"
            or survey.instrument_version_id == (project.metadata_ or {}).get("instrument_version_id")
        )
        study_type = payload.study_type
        barem_id = None
        analytics_plan_id = None
        plan = (
            await self.session.execute(
                select(AnalyticsPlan).where(
                    AnalyticsPlan.code == payload.analytics_plan,
                    AnalyticsPlan.is_active.is_(True),
                )
            )
        ).scalars().first()
        if plan is None and is_censopas_campaign:
            raise ValidationDomainError(f"El plan analítico '{payload.analytics_plan}' no está disponible.")
        analytics_plan_id = plan.id if plan is not None else None
        if is_censopas_campaign:
            study_type = "CENSO"
            configured_barem_id = (project.metadata_ or {}).get("barem_id")
            if configured_barem_id is not None:
                barem = await self.session.get(Barem, int(configured_barem_id))
                if barem is None or barem.instrument_version_id != survey.instrument_version_id:
                    raise ValidationDomainError(
                        "El baremo automático CensoPÁS no corresponde al formulario del proyecto."
                    )
                barem_id = barem.id

        study = Study(
            project_id=project_id,
            survey_id=payload.survey_id,
            instrument_version_id=survey.instrument_version_id,
            name=payload.name,
            study_type=study_type,
            barem_id=barem_id,
            analytics_plan_id=analytics_plan_id,
            start_at=payload.start_at,
            end_at=payload.end_at,
            min_publishable_n=payload.min_publishable_n,
            settings=payload.settings,
            requires_invitation=payload.requires_invitation,
        )
        study = await self.repo.create(study)
        await self.audit.log(
            action="STUDY_CREATED", entity_type="study", entity_id=study.id, project_id=project_id
        )
        await self.session.commit()
        return await self.get(study.id)

    async def list_unit_types(self, study_id: int) -> list[StudyUnitType]:
        await self.get(study_id)
        stmt = (
            select(StudyUnitType)
            .where(StudyUnitType.study_id == study_id)
            .order_by(StudyUnitType.sort_order, StudyUnitType.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def create_unit_type(
        self, study_id: int, payload: StudyUnitTypeCreate
    ) -> StudyUnitType:
        study = await self.get(study_id)
        if study.status != "DRAFT":
            raise ConflictError(
                "Los tipos de unidad deben configurarse antes de abrir el estudio.",
                current_status=study.status,
            )
        exists = await self.session.execute(
            select(StudyUnitType.id).where(
                StudyUnitType.study_id == study_id,
                StudyUnitType.code == payload.code,
            )
        )
        if exists.scalar_one_or_none() is not None:
            raise ValidationDomainError("El código de tipo de unidad ya existe en el estudio.")
        unit_type = StudyUnitType(
            study_id=study_id,
            code=payload.code,
            name=payload.name,
            is_sensitive=payload.is_sensitive,
            sort_order=payload.sort_order,
            metadata_=payload.metadata,
        )
        self.session.add(unit_type)
        await self.session.commit()
        await self.session.refresh(unit_type)
        return unit_type

    async def list_units(self, unit_type_id: int) -> list[StudyUnit]:
        unit_type = await self.session.get(StudyUnitType, unit_type_id)
        if unit_type is None:
            raise NotFoundError(f"Tipo de unidad {unit_type_id} no encontrado")
        stmt = (
            select(StudyUnit)
            .where(StudyUnit.study_unit_type_id == unit_type_id)
            .order_by(StudyUnit.name, StudyUnit.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def create_unit(
        self, unit_type_id: int, payload: StudyUnitCreate
    ) -> StudyUnit:
        unit_type = await self.session.get(StudyUnitType, unit_type_id)
        if unit_type is None:
            raise NotFoundError(f"Tipo de unidad {unit_type_id} no encontrado")
        study = await self.get(unit_type.study_id)
        if study.status != "DRAFT":
            raise ConflictError(
                "Las unidades deben configurarse antes de abrir el estudio.",
                current_status=study.status,
            )
        if payload.parent_id is not None:
            parent = await self.session.get(StudyUnit, payload.parent_id)
            if parent is None or parent.study_unit_type_id != unit_type_id:
                raise ValidationDomainError(
                    "La unidad padre debe pertenecer al mismo tipo de unidad."
                )
        if payload.code is not None:
            existing = await self.session.execute(
                select(StudyUnit.id).where(
                    StudyUnit.study_unit_type_id == unit_type_id,
                    StudyUnit.code == payload.code,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValidationDomainError("El código de unidad ya existe en este tipo.")
        unit = StudyUnit(
            study_unit_type_id=unit_type_id,
            code=payload.code,
            name=payload.name,
            parent_id=payload.parent_id,
            is_active=payload.is_active,
            metadata_=payload.metadata,
        )
        self.session.add(unit)
        await self.session.commit()
        await self.session.refresh(unit)
        return unit

    async def get(self, study_id: int) -> Study:
        study = await self.repo.get(study_id)
        if study is None:
            raise NotFoundError(f"Estudio {study_id} no encontrado")
        return study

    async def list_by_project(self, project_id: int, params: PageParams) -> Page[StudyRead]:
        items, total = await paginate(self.session, self.repo.list_by_project_stmt(project_id), params)
        return Page[StudyRead](
            items=[StudyRead.model_validate(item) for item in items],
            page=params.page,
            page_size=params.page_size,
            total=total,
        )

    async def update(self, study_id: int, payload: StudyUpdate) -> Study:
        study = await self.get(study_id)
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(study, field, value)
        await self.session.commit()
        return await self.get(study.id)

    def _transition(self, study: Study, target: str) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(study.status)
        if allowed != target:
            raise ConflictError(
                f"No se puede pasar el estudio de {study.status} a {target}.",
                current_status=study.status,
                target_status=target,
            )

    async def _is_enterprise_evaluation(self, study: Study, project: Project | None = None) -> bool:
        if project is None:
            project = await self.session.get(Project, study.project_id)
        if project is None:
            return False

        # Si el proyecto no pertenece a ninguna organización empresarial, es investigación libre / personal
        if project.organization_id is None:
            return False

        # Criterio A1: La condición de evaluación empresarial se deriva de relaciones confiables del backend:
        # 1. Pertenencia a organización y tipo de proyecto corporativo/empresarial (no académico)
        if project.project_type != "ACADEMIC":
            return True

        # 2. Si el proyecto se declaró ACADEMIC pero el estudio tiene características explícitas de evaluación corporativa:
        has_enterprise_settings = bool(
            study.settings.get("is_enterprise_evaluation")
            or study.settings.get("enterprise_campaign")
            or study.settings.get("is_enterprise")
        )
        if has_enterprise_settings:
            return True

        return False

    async def require_current_enterprise_method(self, study: Study) -> None:
        """Recheck revocable catalog authorization, without changing personal studies.

        OPEN is a lifecycle state, not a permanent authorization grant. Official
        system versions may remain LOCKED (immutable) while their instrument is
        active; private versions must remain ACTIVE/AUTHORIZED and configured.
        """
        if not await self._is_enterprise_evaluation(study):
            return
        version = (
            await self.instrument_repo.get_version_with_instrument(study.instrument_version_id)
            if study.instrument_version_id is not None else None
        )
        if version is None or version.instrument is None:
            raise ValidationDomainError("El método empresarial no está disponible.")
        instrument = version.instrument
        allowed_versions = {"AUTHORIZED", "ACTIVE"}
        if instrument.is_system:
            allowed_versions.add("LOCKED")
        if instrument.status not in {"AUTHORIZED", "ACTIVE"}:
            raise ValidationDomainError("El instrumento no está en estado AUTHORIZED o ACTIVE.")
        if version.status not in allowed_versions:
            raise ValidationDomainError("La versión del instrumento no está en estado AUTHORIZED o ACTIVE.")
        if not instrument.is_system and version.scoring_status != "CONFIGURED":
            raise ValidationDomainError("El método empresarial no tiene configuración de puntuación vigente.")

    async def open(self, study_id: int) -> Study:
        """harness §15: al abrir un estudio se valida survey/instrument_version,
        se congela una snapshot de configuración y se impiden cambios
        destructivos posteriores (delegado a InstrumentEditPolicy)."""
        study = await self.get(study_id)
        self._transition(study, "OPEN")
        await self.require_current_enterprise_method(study)

        survey_stmt = (
            select(Survey)
            .where(Survey.id == study.survey_id)
            .options(
                selectinload(Survey.sections),
                selectinload(Survey.survey_questions)
                .selectinload(SurveyQuestion.question)
                .selectinload(Question.option_set)
                .selectinload(OptionSet.options),
            )
        )
        survey = (await self.session.execute(survey_stmt)).scalar_one_or_none()
        if survey is None:
            raise NotFoundError(f"Survey {study.survey_id} no encontrado")

        if survey.instrument_version_id is not None and survey.instrument_version_id != study.instrument_version_id:
            survey_version = await self.instrument_repo.get_version_with_instrument(
                survey.instrument_version_id
            )
            if survey_version is not None and survey_version.instrument is not None:
                if survey_version.instrument.code == "CENSOPAS_COPSOQ":
                    await self._validate_censopas_survey_completeness(
                        survey, survey_version, study.instrument_version_id
                    )

        for link in survey.survey_questions:
            question = link.question
            if not question.is_scored:
                continue
            if question.question_type != "LIKERT" or question.option_set is None:
                raise ValidationDomainError(
                    f"El ítem puntuable {question.code or question.id} no tiene una escala Likert."
                )
            active_options = [option for option in question.option_set.options if option.is_active]
            if len(active_options) < 2 or any(
                option.numeric_value is None for option in active_options
            ):
                raise ValidationDomainError(
                    f"La escala de {question.code or question.id} necesita al menos dos "
                    "opciones activas con valor numérico."
                )

        snapshot_data: dict = {
            "survey": {
                "id": survey.id,
                "name": survey.name,
                "survey_type": survey.survey_type,
                "settings": survey.settings,
                "sections": [
                    {
                        "id": section.id,
                        "title": section.title,
                        "section_kind": section.section_kind,
                        "sort_order": section.sort_order,
                    }
                    for section in sorted(survey.sections, key=lambda item: (item.sort_order, item.id))
                ],
                "questions": [
                    {
                        "id": link.question.id,
                        "code": link.question.code,
                        "text": link.display_text_override or link.question.question_text,
                        "question_type": link.question.question_type,
                        "is_scored": link.question.is_scored,
                        "research_role": link.question.research_role,
                        "section_id": link.section_id,
                        "sort_order": link.sort_order,
                        "is_required": (
                            link.is_required
                            if link.is_required is not None
                            else link.question.is_required_default
                        ),
                        "option_set": (
                            {
                                "id": link.question.option_set.id,
                                "code": link.question.option_set.code,
                                "name": link.question.option_set.name,
                                "options": [
                                    {
                                        "raw_code": option.raw_code,
                                        "label": option.label,
                                        "numeric_value": (
                                            float(option.numeric_value)
                                            if option.numeric_value is not None
                                            else None
                                        ),
                                        "sort_order": option.sort_order,
                                    }
                                    for option in link.question.option_set.options
                                    if option.is_active
                                ],
                            }
                            if link.question.option_set
                            else None
                        ),
                    }
                    for link in sorted(survey.survey_questions, key=lambda item: item.sort_order)
                ],
            }
        }

        project = await self.session.get(Project, study.project_id)
        is_enterprise = await self._is_enterprise_evaluation(study, project)

        if study.instrument_version_id is not None:
            version = await self.instrument_repo.get_version_with_instrument(
                study.instrument_version_id
            )
            if version is None:
                raise NotFoundError(
                    f"Versión de instrumento {study.instrument_version_id} no encontrada"
                )
            await self._validate_censopas_survey_completeness(
                survey, version, study.instrument_version_id
            )
            instrument = version.instrument

            # Aislamiento multiempresa (A1):
            if not getattr(instrument, "is_system", False) and project is not None and project.organization_id is not None:
                if instrument.organization_id is not None and instrument.organization_id != project.organization_id:
                    raise AuthorizationError(
                        "Aislamiento multiempresa: el instrumento pertenece a otra organización y no puede asignarse a este estudio."
                    )
                if instrument.organization_id is None and instrument.project_id is not None and instrument.project_id != project.id:
                    raise AuthorizationError(
                        "Aislamiento multiempresa: el instrumento está restringido a otro proyecto."
                    )

            if is_enterprise and not getattr(instrument, "is_system", False):
                if version.status not in ("AUTHORIZED", "ACTIVE"):
                    raise ValidationDomainError(
                        f"No se puede abrir el estudio empresarial: la versión del instrumento '{version.version_code}' "
                        f"no está en estado AUTHORIZED o ACTIVE (estado actual: {version.status})."
                    )
                if version.scoring_status != "CONFIGURED":
                    raise ValidationDomainError(
                        f"No se puede abrir el estudio empresarial: la versión del instrumento '{version.version_code}' "
                        f"tiene scoring_status='{version.scoring_status}'. Debe estar en estado CONFIGURED."
                    )

            if is_enterprise:
                # Reglas metodológicas válidas (A1): verificar que existan constructos
                construct_count_stmt = select(Construct.id).where(
                    Construct.instrument_version_id == version.id
                )
                first_construct = (await self.session.execute(construct_count_stmt)).scalars().first()
                if first_construct is None:
                    raise ValidationDomainError(
                        "La versión del instrumento no tiene constructos metodológicos configurados."
                    )
                if study.barem_id is not None:
                    barem = await self.session.get(Barem, study.barem_id)
                    if barem is None or barem.instrument_version_id != version.id:
                        raise ValidationDomainError(
                            "El baremo asignado no corresponde a la versión del instrumento del estudio."
                        )

            snapshot_data["instrument_version"] = {
                "id": version.id,
                "version_code": version.version_code,
                "status": version.status,
                "config": version.config,
            }

            construct_stmt = (
                select(Construct)
                .where(Construct.instrument_version_id == version.id)
                .options(selectinload(Construct.item_links))
                .order_by(Construct.sort_order, Construct.id)
            )
            constructs = list((await self.session.execute(construct_stmt)).scalars().all())
            snapshot_data["constructs"] = [
                {
                    "id": construct.id,
                    "parent_id": construct.parent_id,
                    "code": construct.code,
                    "name": construct.name,
                    "construct_type": construct.construct_type,
                    "items": [
                        {
                            "question_id": link.question_id,
                            "weight": float(link.weight),
                            "item_role": link.item_role,
                            "scoring_direction": link.scoring_direction,
                        }
                        for link in construct.item_links
                    ],
                }
                for construct in constructs
            ]

            rules_stmt = select(ScoringRule).where(ScoringRule.instrument_version_id == version.id)
            rules = list((await self.session.execute(rules_stmt)).scalars().all())
            snapshot_data["scoring_rules"] = [
                {
                    "id": rule.id,
                    "question_id": rule.question_id,
                    "construct_id": rule.construct_id,
                    "rule_type": rule.rule_type,
                    "parameters": rule.parameters,
                    "rule_version": rule.rule_version,
                    "status": rule.status,
                }
                for rule in rules
            ]

            exogenous_stmt = select(Variable).where(
                Variable.project_id == study.project_id,
                Variable.instrument_version_id == version.id,
                Variable.variable_type == "EXOGENOUS",
            )
            exogenous = list((await self.session.execute(exogenous_stmt)).scalars().all())
            snapshot_data["exogenous_variables"] = [
                {
                    "id": variable.id,
                    "question_id": variable.question_id,
                    "code": variable.code,
                    "name": variable.name,
                    "data_type": variable.data_type,
                    "measurement_level": variable.measurement_level,
                }
                for variable in exogenous
            ]

        if study.barem_id is not None:
            barem_stmt = (
                select(Barem)
                .where(Barem.id == study.barem_id)
                .options(selectinload(Barem.bands), selectinload(Barem.cutoffs))
            )
            barem = (await self.session.execute(barem_stmt)).scalar_one_or_none()
            if barem is None:
                raise NotFoundError(f"Baremo {study.barem_id} no encontrado")
            snapshot_data["barem"] = {
                "id": barem.id,
                "name": barem.name,
                "population_label": barem.population_label,
                "source_reference": barem.source_reference,
                "barem_version": barem.barem_version,
                "status": barem.status,
                "bands": [
                    {
                        "id": band.id,
                        "construct_id": band.construct_id,
                        "code": band.code,
                        "label": band.label,
                        "min_value": float(band.min_value),
                        "max_value": float(band.max_value),
                        "severity_order": band.severity_order,
                        "interpretation": band.interpretation,
                        "color_hint": band.color_hint,
                        "classification_code": band.classification_code,
                    }
                    for band in barem.bands
                ],
            }

        unit_types_stmt = (
            select(StudyUnitType)
            .where(StudyUnitType.study_id == study.id)
            .order_by(StudyUnitType.sort_order, StudyUnitType.id)
        )
        unit_types = list((await self.session.execute(unit_types_stmt)).scalars().all())
        unit_type_ids = [ut.id for ut in unit_types]
        study_units: list[StudyUnit] = []
        if unit_type_ids:
            units_stmt = (
                select(StudyUnit)
                .where(StudyUnit.study_unit_type_id.in_(unit_type_ids))
                .order_by(StudyUnit.study_unit_type_id, StudyUnit.name, StudyUnit.id)
            )
            study_units = list((await self.session.execute(units_stmt)).scalars().all())

        snapshot_data["organizational_structure"] = {
            "unit_types": [
                {
                    "id": ut.id,
                    "code": ut.code,
                    "name": ut.name,
                    "is_sensitive": ut.is_sensitive,
                    "sort_order": ut.sort_order,
                }
                for ut in unit_types
            ],
            "units": [
                {
                    "id": u.id,
                    "study_unit_type_id": u.study_unit_type_id,
                    "code": u.code,
                    "name": u.name,
                    "parent_id": u.parent_id,
                    "is_active": u.is_active,
                }
                for u in study_units
            ],
        }

        payload_bytes = json.dumps(snapshot_data, sort_keys=True, default=str).encode("utf-8")
        sha256_hash = hashlib.sha256(payload_bytes).hexdigest()

        snapshot = StudySnapshot(
            study_id=study.id,
            snapshot_type="STUDY_OPEN",
            snapshot_data=snapshot_data,
            sha256_hash=sha256_hash,
        )
        await self.repo.add_snapshot(snapshot)

        study.status = "OPEN"
        study.start_at = study.start_at or datetime.now(UTC)
        await self.session.flush()
        await self.audit.log(
            action="STUDY_OPENED", entity_type="study", entity_id=study.id, project_id=study.project_id
        )
        await self.session.commit()
        return await self.get(study.id)

    async def close(self, study_id: int) -> Study:
        study = await self.get(study_id)
        self._transition(study, "CLOSED")
        study.status = "CLOSED"
        study.end_at = study.end_at or datetime.now(UTC)
        await self.session.flush()
        await self.audit.log(
            action="STUDY_CLOSED", entity_type="study", entity_id=study.id, project_id=study.project_id
        )
        await self.session.commit()
        return await self.get(study.id)

    async def archive(self, study_id: int) -> Study:
        study = await self.get(study_id)
        self._transition(study, "ARCHIVED")
        study.status = "ARCHIVED"
        await self.session.flush()
        await self.audit.log(
            action="STUDY_ARCHIVED", entity_type="study", entity_id=study.id, project_id=study.project_id
        )
        await self.session.commit()
        return await self.get(study.id)
