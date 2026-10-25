"""Catalog selection must never silently resolve to another published version."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationDomainError
from app.schemas.projects import CensopasStudyConfig
from app.api.v1.quick_eval import QuickEvalRequest
from app.services.censopas_provisioning_service import CensopasProvisioningService


@pytest.mark.asyncio
async def test_exact_catalog_version_is_preserved_even_with_newer_version():
    older = SimpleNamespace(id=10, config={"censopas_version_kind": "SHORT"})
    newer = SimpleNamespace(id=20, config={"censopas_version_kind": "SHORT"})
    result = MagicMock()
    result.scalars.return_value.all.return_value = [newer, older]
    service = CensopasProvisioningService(SimpleNamespace(execute=AsyncMock(return_value=result)))
    assert await service._default_version("SHORT", 10) is older
    assert await service._default_version("SHORT") is newer


@pytest.mark.asyncio
async def test_missing_or_wrong_kind_version_does_not_fallback():
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        SimpleNamespace(id=20, config={"censopas_version_kind": "MEDIUM"})
    ]
    service = CensopasProvisioningService(SimpleNamespace(execute=AsyncMock(return_value=result)))
    with pytest.raises(ValidationDomainError):
        await service._default_version("SHORT", 20)
    with pytest.raises(ValidationDomainError):
        await service._default_version("MEDIUM", 10)


def test_quick_eval_and_project_config_accept_exact_version_id():
    request = QuickEvalRequest(company_name="Synthetic", company_ruc="TEST-001",
                               instrument_version="SHORT", instrument_version_id=10,
                               study_name="Synthetic study")
    config = CensopasStudyConfig(instrument_version=request.instrument_version,
                                instrument_version_id=request.instrument_version_id)
    assert config.instrument_version_id == 10
