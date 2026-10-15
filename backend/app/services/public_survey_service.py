from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import PublicResourceUnavailableError
from app.models.option_set import OptionSet
from app.models.participant import StudyInvitation
from app.models.question import Question
from app.models.response import ResponseSession
from app.models.survey import Survey, SurveyQuestion
from app.repositories.projects import ProjectRepository
from app.repositories.responses import ResponseRepository
from app.repositories.studies import StudyRepository
from app.schemas.public import PublicOption, PublicQuestion, PublicSection, PublicSurveyBundle
from app.services.audit_service import AuditService
from app.services.invitation_service import hash_invitation_token

_UNAVAILABLE_MESSAGE = "Esta encuesta no está disponible o ya no acepta respuestas."


class PublicSurveyService:
    """Resolución de estudios por `public_id` para el formulario público
    (sin autenticación, sin exponer ids internos ni datos del propietario)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.study_repo = StudyRepository(session)
        self.response_repo = ResponseRepository(session)
        self.project_repo = ProjectRepository(session)
        self.audit = AuditService(session)

    async def _require_open_study(self, public_id: uuid.UUID):
        study = await self.study_repo.get_by_public_id(public_id)
        if study is None or study.status != "OPEN":
            raise PublicResourceUnavailableError(_UNAVAILABLE_MESSAGE)
        if study.end_at is not None:
            end_at = study.end_at if study.end_at.tzinfo else study.end_at.replace(tzinfo=UTC)
            if datetime.now(UTC) >= end_at:
                raise PublicResourceUnavailableError(_UNAVAILABLE_MESSAGE)
        return study

    async def _consume_invitation(self, study_id: int, token: str | None) -> StudyInvitation | None:
        if not token:
            return None
        stmt = select(StudyInvitation).where(
            StudyInvitation.study_id == study_id,
            StudyInvitation.access_token_hash == hash_invitation_token(token),
            StudyInvitation.status.in_(("PENDING", "SENT")),
        )
        # PostgreSQL row lock prevents double-use when two workers redeem the same code.
        if self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        invitation = (await self.session.execute(stmt)).scalar_one_or_none()
        if invitation is None:
            return None
        if invitation.expires_at is not None:
            expires_at = (
                invitation.expires_at
                if invitation.expires_at.tzinfo
                else invitation.expires_at.replace(tzinfo=UTC)
            )
            if datetime.now(UTC) >= expires_at:
                return None
        # Deliberadamente no se guarda qué response_session resultó: la
        # invitación sólo autentica la creación, nunca queda ligada al
        # contenido de la respuesta (harness §12).
        invitation.status = "CONSUMED"
        invitation.consumed_at = datetime.now(UTC)
        return invitation

    async def get_open_study_bundle(self, public_id: uuid.UUID) -> PublicSurveyBundle:
        study = await self._require_open_study(public_id)

        stmt = (
            select(Survey)
            .where(Survey.id == study.survey_id)
            .options(
                selectinload(Survey.sections),
                selectinload(Survey.survey_questions)
                .selectinload(SurveyQuestion.question)
                .selectinload(Question.option_set)
                .selectinload(OptionSet.options)
            )
        )
        survey = (await self.session.execute(stmt)).scalar_one_or_none()
        if survey is None:
            raise PublicResourceUnavailableError(_UNAVAILABLE_MESSAGE)

        # El estilo se guarda en el proyecto (paso Formulario del builder),
        # no en `survey.settings`: un proyecto puede acumular varias filas
        # de Survey a lo largo del tiempo (cada "crear formulario" crea una
        # nueva) y el Study público puede haber quedado abierto contra una
        # más vieja que la que el builder sigue editando vía
        # `project.metadata.survey_id` — leer del proyecto evita que el
        # estilo dependa de cuál de esas filas resultó ser la pública.
        project = await self.project_repo.get(study.project_id)
        theme = (project.metadata_.get("form_theme") if project else None) or {}

        ordered_links = sorted(survey.survey_questions, key=lambda link: link.sort_order)
        questions = [
            PublicQuestion(
                id=link.question.id,
                code=link.question.code,
                question_text=link.display_text_override or link.question.question_text,
                short_label=link.question.short_label,
                question_type=link.question.question_type,
                is_scored=link.question.is_scored,
                research_role=link.question.research_role,
                is_required=(
                    link.is_required
                    if link.is_required is not None
                    else link.question.is_required_default
                ),
                validation_rules=link.question.validation_rules,
                options=(
                    [
                        PublicOption.model_validate(option)
                        for option in link.question.option_set.options
                        if option.is_active
                    ]
                    if link.question.option_set
                    else []
                ),
            )
            for link in ordered_links
        ]
        question_by_id = {question.id: question for question in questions}
        section_links: dict[int | None, list[PublicQuestion]] = {}
        for link in ordered_links:
            section_links.setdefault(link.section_id, []).append(question_by_id[link.question.id])

        sections = [
            PublicSection(
                id=section.id,
                title=section.title,
                description=section.description,
                section_kind=section.section_kind,
                sort_order=section.sort_order,
                questions=section_links.get(section.id, []),
            )
            for section in sorted(survey.sections, key=lambda item: (item.sort_order, item.id))
            if section_links.get(section.id)
        ]
        if section_links.get(None):
            sections.append(
                PublicSection(
                    id=0,
                    title="Cuestionario",
                    description=None,
                    section_kind="INSTRUMENT",
                    sort_order=len(sections),
                    questions=section_links[None],
                )
            )

        return PublicSurveyBundle(
            study_public_id=study.public_id,
            requires_invitation=study.requires_invitation,
            study_name=study.name,
            survey_name=survey.name,
            survey_description=survey.description,
            questions=questions,
            sections=sections,
            theme=theme,
        )

    async def create_session_for_public_study(
        self, public_id: uuid.UUID, invitation_token: str | None = None
    ) -> ResponseSession:
        study = await self._require_open_study(public_id)
        if study.requires_invitation:
            invitation = await self._consume_invitation(study.id, invitation_token)
            if invitation is None:
                # Mismo mensaje/código que "estudio no disponible" (E-17):
                # no darle a un respondiente anónimo forma de distinguir
                # "el link está mal" de "el token ya se usó/expiró".
                raise PublicResourceUnavailableError(_UNAVAILABLE_MESSAGE)
        response_session = ResponseSession(study_id=study.id)
        response_session = await self.response_repo.create_session(response_session)
        await self.audit.log(
            action="PUBLIC_RESPONSE_SESSION_CREATED",
            entity_type="response_session",
            entity_id=None,
        )
        await self.session.commit()
        await self.session.refresh(response_session)
        return response_session
