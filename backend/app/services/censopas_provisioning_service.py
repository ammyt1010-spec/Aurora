"""Aprovisionamiento fijo de un proyecto empresarial CensoPÁS.

El banco oficial vive una sola vez en el backend como instrumento de sistema.
Cada proyecto CENSO sólo recibe referencias a esa versión, sus variables
exógenas por proyecto y un baremo de referencia (nunca oficial).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.analytics.censopas.classification import cutoff_to_bands
from app.core.exceptions import ValidationDomainError
from app.models.censopas import Barem, BaremBand, BaremCutoff
from app.models.construct import Construct
from app.models.instrument import Instrument, InstrumentVersion
from app.models.project import Project
from app.models.question import Question
from app.models.survey import Survey, SurveyQuestion, SurveySection
from app.models.variable import Variable
from app.services.scoring_service import ScoringService


REFERENCE_BAREM_CODE = "CENSOPAS_REFERENCE_TERCILES_V1"

# El nivel de medición es parte de la convención del instrumento, no se
# infiere del numeric_value de las opciones (una categoría nominal también
# puede tener códigos numéricos).
_ORDINAL_CODES = {"C-002", "C-003", "C-007", "C-009", "C-011"}
_BINARY_CODES = {"C-001"}


class CensopasProvisioningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def provision_project(self, project: Project) -> None:
        """Vincula el plan corto listo y materializa los datos del proyecto.

        Se invoca dentro de la misma transacción que crea el proyecto: si el
        catálogo oficial no está desplegado, no queda un CENSO a medio crear.
        """
        requested_kind = (project.metadata_ or {}).get("requested_version_kind", "SHORT")
        if requested_kind not in ("SHORT", "MEDIUM"):
            raise ValidationDomainError(
                f"requested_version_kind inválido: '{requested_kind}'. Debe ser 'SHORT' o 'MEDIUM'.",
                convention="CENSOPAS_PROJECT_PROVISIONING",
            )
        version = await self._default_version(
            requested_kind, (project.metadata_ or {}).get("requested_version_id")
        )
        version_questions = await self._version_questions(version.id)
        exogenous_questions = [
            question
            for question in version_questions
            if question.research_role == "EXOGENOUS" and not question.is_scored
        ]
        if not exogenous_questions:
            raise ValidationDomainError(
                "La versión oficial CensoPÁS no contiene los datos exógenos fijos. "
                "Ejecute scripts/seed_censopas_official.py antes de crear el proyecto.",
                convention="CENSOPAS_PROJECT_PROVISIONING",
            )

        await self._ensure_exogenous_variables(project, version, exogenous_questions)
        # The exogenous subset feeds project variables only. The survey must
        # preserve every item from the selected immutable version, including
        # scored items and contextual items.
        survey = await self._ensure_survey(project, version, version_questions)
        barem = await self._ensure_reference_barem(project, version)

        project.metadata_ = {
            **(project.metadata_ or {}),
            "instrument_id": version.instrument_id,
            "instrument_version_id": version.id,
            "censopas_version_kind": (version.config or {}).get(
                "censopas_version_kind", "SHORT"
            ),
            "barem_id": barem.id,
            "survey_id": survey.id,
            "censopas_auto_provisioned": True,
            "censopas_provisioning_version": "v1",
        }
        await self.session.flush()

    async def _default_version(self, version_kind: str, version_id: int | None = None) -> InstrumentVersion:
        stmt = (
            select(InstrumentVersion)
            .join(Instrument, InstrumentVersion.instrument_id == Instrument.id)
            .where(
                Instrument.is_system.is_(True),
                Instrument.code == "CENSOPAS_COPSOQ",
                InstrumentVersion.status.in_(("ACTIVE", "LOCKED")),
            )
            .options(selectinload(InstrumentVersion.instrument))
            .order_by(InstrumentVersion.id.desc())
        )
        versions = list((await self.session.execute(stmt)).scalars().all())
        version = next(
            (
                item
                for item in versions
                if (item.config or {}).get("censopas_version_kind") == version_kind
                and (version_id is None or item.id == version_id)
            ),
            None,
        )
        if version is None:
            raise ValidationDomainError(
                f"No existe un plan CensoPÁS oficial ({version_kind}), activo y protegido en "
                "el backend. Ejecute scripts/seed_censopas_official.py antes de crear el proyecto.",
                convention="CENSOPAS_PROJECT_PROVISIONING",
            )
        return version

    async def _version_questions(self, version_id: int) -> list[Question]:
        stmt = (
            select(Question)
            .where(Question.instrument_version_id == version_id)
            .order_by(Question.sort_order, Question.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def _ensure_exogenous_variables(
        self,
        project: Project,
        version: InstrumentVersion,
        questions: list[Question],
    ) -> None:
        existing_stmt = select(Variable.code).where(Variable.project_id == project.id)
        existing_codes = set((await self.session.execute(existing_stmt)).scalars().all())
        for question in questions:
            code = question.code or f"CENSOPAS_EXO_{question.id}"
            if code in existing_codes:
                continue
            if question.question_type == "TEXT":
                data_type, measurement_level = "TEXT", "TEXT"
            elif code in _BINARY_CODES:
                data_type, measurement_level = "CATEGORY", "BINARY"
            elif code in _ORDINAL_CODES:
                data_type, measurement_level = "CATEGORY", "ORDINAL"
            else:
                data_type, measurement_level = "CATEGORY", "NOMINAL"
            metadata = question.metadata_ or {}
            self.session.add(
                Variable(
                    project_id=project.id,
                    instrument_version_id=version.id,
                    question_id=question.id,
                    code=code,
                    name=question.short_label or question.question_text,
                    label=question.question_text,
                    variable_type="EXOGENOUS",
                    data_type=data_type,
                    measurement_level=measurement_level,
                    role="EXOGENOUS",
                    is_editable=False,
                    metadata_={
                        "research_role": "EXOGENOUS",
                        "censopas_fixed_catalog": True,
                        "adaptable": bool(metadata.get("adaptable", False)),
                    },
                )
            )
        await self.session.flush()

    async def _ensure_survey(
        self, project: Project, version: InstrumentVersion, questions: list[Question]
    ) -> Survey:
        existing = (
            await self.session.execute(
                select(Survey).where(
                    Survey.project_id == project.id,
                    Survey.instrument_version_id == version.id,
                    Survey.survey_type == "CENSO",
                )
            )
        ).scalars().first()
        if existing is not None:
            return existing

        survey = Survey(
            project_id=project.id,
            instrument_version_id=version.id,
            created_by_user_id=project.owner_user_id,
            name=f"{project.name} — Formulario CensoPÁS",
            description="Formulario CensoPÁS-COPSOQ generado automáticamente desde el instrumento oficial.",
            survey_type="CENSO",
            status="DRAFT",
        )
        self.session.add(survey)
        await self.session.flush()
        exogenous = SurveySection(
            survey_id=survey.id,
            title="Datos de perfil",
            description="Datos exógenos fijos para segmentar resultados; no modifican el puntaje.",
            section_kind="EXOGENOUS",
            sort_order=0,
        )
        instrument = SurveySection(
            survey_id=survey.id,
            title="Instrumento CensoPÁS",
            description="Preguntas y escalas oficiales CENSOPAS-COPSOQ.",
            section_kind="INSTRUMENT",
            sort_order=1,
        )
        self.session.add_all([exogenous, instrument])
        await self.session.flush()
        for index, question in enumerate(
            sorted(
                questions,
                key=lambda item: (
                    item.sort_order if item.sort_order is not None else item.id,
                    item.id,
                ),
            )
        ):
            self.session.add(
                SurveyQuestion(
                    survey_id=survey.id,
                    question_id=question.id,
                    section_id=exogenous.id if question.research_role == "EXOGENOUS" else instrument.id,
                    sort_order=index,
                    is_required=question.is_required_default,
                )
            )
        await self.session.flush()
        return survey

    async def _ensure_reference_barem(
        self, project: Project, version: InstrumentVersion
    ) -> Barem:
        # Un baremo pertenece al proyecto por convención explícita en metadata;
        # no se comparte entre empresas aunque usen la misma versión fija.
        stmt = select(Barem).where(Barem.instrument_version_id == version.id)
        candidates = list((await self.session.execute(stmt)).scalars().all())
        barem = next(
            (
                item
                for item in candidates
                if (item.metadata_ or {}).get("convention_code") == REFERENCE_BAREM_CODE
                and (item.metadata_ or {}).get("project_id") == project.id
            ),
            None,
        )
        if barem is not None:
            return barem

        barem = Barem(
            instrument_version_id=version.id,
            name="Referencia automática por terciles — CensoPÁS",
            population_label="Población del proyecto (referencia provisional)",
            source_reference=(
                "Convención interna Colmena: intervalos iguales 0–33.33–66.67–100. "
                "No equivale a cortes oficiales CENSOPAS-COPSOQ."
            ),
            barem_version="REFERENCE-TERCILES-V1",
            status="ACTIVE",
            metadata_={
                "barem_type": "REFERENCE",
                "convention_code": REFERENCE_BAREM_CODE,
                "project_id": project.id,
                "automatic": True,
                "official_equivalence": False,
            },
        )
        self.session.add(barem)
        await self.session.flush()

        constructs_stmt = (
            select(Construct)
            .where(Construct.instrument_version_id == version.id)
            .options(selectinload(Construct.item_links))
            .order_by(Construct.sort_order, Construct.id)
        )
        constructs = list((await self.session.execute(constructs_stmt)).scalars().all())
        # Una DIMENSION es puntuable aunque no tenga item_links directos: en la
        # versión MEDIA sus ítems cuelgan de las SUBDIMENSION hijas. Sin este
        # resolver descendiente, D1-D6 quedaban sin baremo en esa versión
        # (bands=[] aguas abajo) mientras S1-S20 sí lo recibían.
        effective_links = ScoringService.resolve_effective_item_links(constructs)
        scored = [item for item in constructs if effective_links[item.id]]
        if not scored:
            raise ValidationDomainError(
                "La versión oficial CensoPÁS no contiene dimensiones puntuables.",
                convention="CENSOPAS_PROJECT_PROVISIONING",
            )

        for construct in scored:
            cutoff = BaremCutoff(
                barem_id=barem.id,
                construct_id=construct.id,
                cut_1=33.333333,
                cut_2=66.666667,
                direction="LOWER_BETTER",
                favorable_label="FAVORABLE",
                intermediate_label="INTERMEDIO",
                unfavorable_label="DESFAVORABLE",
                metadata_={"reference_only": True, "automatic": True},
            )
            self.session.add(cutoff)
            for band_kwargs in cutoff_to_bands(
                cutoff.cut_1,
                cutoff.cut_2,
                cutoff.direction,
                cutoff.favorable_label,
                cutoff.intermediate_label,
                cutoff.unfavorable_label,
            ):
                self.session.add(
                    BaremBand(
                        barem_id=barem.id,
                        construct_id=construct.id,
                        interpretation="Clasificación de referencia; no es equivalencia oficial.",
                        metadata_={"reference_only": True, "automatic": True},
                        **band_kwargs,
                    )
                )
        await self.session.flush()
        return barem
