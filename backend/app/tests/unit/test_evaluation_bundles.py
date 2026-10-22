from types import SimpleNamespace
import uuid
import pytest

from app.api.v1.evaluation_bundles import _validate_studies
from app.core.exceptions import ValidationDomainError


def study(id, project_id=2, status="OPEN", requires_invitation=False):
    return SimpleNamespace(
        id=id, project_id=project_id, status=status,
        requires_invitation=requires_invitation,
        public_id=uuid.uuid4(), start_at=None, end_at=None, instrument_version_id=1,
    )


def test_rejects_cross_company_study():
    with pytest.raises(ValidationDomainError):
        _validate_studies([study(1), study(2, project_id=5)], 2, [1, 2])


def test_never_ignores_invitation_gates():
    with pytest.raises(ValidationDomainError):
        _validate_studies([study(1), study(2, requires_invitation=True)], 2, [1, 2])


def test_does_not_publish_closed_studies_or_duplicate_ids():
    for other in [study(2, status="CLOSED"), study(2, status="DRAFT")]:
        with pytest.raises(ValidationDomainError):
            _validate_studies([study(1), other], 2, [1, 2])
    with pytest.raises(ValidationDomainError):
        _validate_studies([study(1)], 2, [1, 1])


def test_accepts_two_authorized_public_studies():
    _validate_studies([study(1), study(2)], 2, [1, 2])
