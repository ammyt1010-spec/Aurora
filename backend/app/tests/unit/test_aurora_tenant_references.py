"""Cross-tenant JSON reference validation, separate from trusted legacy fixtures."""
import pytest

from app.core.business_access import validate_payload_references
from app.core.exceptions import AuthorizationError
from app.models.instrument import Instrument, InstrumentVersion
from app.models.survey import Survey
from app.models.user import User
from app.models.project import Project


@pytest.mark.asyncio
async def test_study_cannot_use_survey_from_other_project(session, seed_project, seed_user):
    outsider_project = Project(owner_user_id=seed_user.id, name="Proyecto B", project_type="ACADEMIC", status="DRAFT")
    session.add(outsider_project)
    await session.flush()
    survey = Survey(
        project_id=outsider_project.id, created_by_user_id=seed_user.id,
        name="Externo", survey_type="CUSTOM", status="DRAFT",
    )
    session.add(survey)
    await session.commit()
    with pytest.raises(AuthorizationError, match="otro proyecto"):
        await validate_payload_references(
            session, seed_user, {"project_id": str(seed_project.id)},
            {"survey_id": survey.id}
        )


@pytest.mark.asyncio
async def test_foreign_private_instrument_version_denied(session, seed_project, seed_user):
    owner = User(email="other@aurora.test", username="other-test", status="ACTIVE")
    session.add(owner)
    await session.flush()
    instr = Instrument(owner_user_id=owner.id, name="Externo", is_system=False)
    session.add(instr)
    await session.flush()
    version = InstrumentVersion(instrument_id=instr.id, version_code="V1")
    session.add(version)
    await session.commit()
    with pytest.raises(AuthorizationError):
        await validate_payload_references(
            session, seed_user, {"project_id": str(seed_project.id)},
            {"instrument_version_id": version.id}
        )
