"""Regresión de la política global de acceso para nuevas rutas de reportes PR #16.

Pruebas directas de require_business_access: los fixtures HTTP del resto del
proyecto pueden sustituir dependencias y ocultar una ruta no reconocida.
"""
import pytest
from starlette.requests import Request

from app.core.business_access import require_business_access
from app.core.config import get_settings
from app.core.exceptions import AuthorizationError
from app.models.report import ReportTemplate
from app.models.user import Organization, OrganizationMembership


def route_request(method: str, path: str, **params) -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "scheme": "http",
        "path_params": {k: str(v) for k, v in params.items()},
    })


@pytest.mark.asyncio
async def test_published_report_template_is_readable_but_only_operator_can_edit(
    session, seed_user, monkeypatch
):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", None)
    template = ReportTemplate(
        name="Plantilla de prueba",
        report_type="ERGONOMIA",
        status="ACTIVE",
    )
    session.add(template)
    await session.flush()

    read = route_request(
        "GET", f"/api/v1/report-templates/{template.id}", template_id=template.id
    )
    await require_business_access(read, db=session, user=seed_user)

    edit = route_request(
        "PUT", f"/api/v1/report-templates/{template.id}", template_id=template.id
    )
    with pytest.raises(AuthorizationError):
        await require_business_access(edit, db=session, user=seed_user)

    template.status = "DRAFT"
    await session.flush()
    with pytest.raises(AuthorizationError):
        await require_business_access(read, db=session, user=seed_user)


@pytest.mark.asyncio
async def test_report_history_access_requires_matching_enterprise_admin(
    session, seed_user, monkeypatch
):
    monkeypatch.setattr(get_settings(), "billing_operator_user_id", None)
    own = Organization(name="Empresa autorizada", tax_id="20999888001")
    foreign = Organization(name="Empresa de tercero", tax_id="20999888002")
    session.add_all([own, foreign])
    await session.flush()
    session.add(OrganizationMembership(
        organization_id=own.id,
        user_id=seed_user.id,
        role_code="OWNER",
        permissions={},
    ))
    await session.flush()

    allowed = route_request(
        "GET",
        f"/api/v1/organizations/{own.id}/reports/history",
        organization_id=own.id,
    )
    await require_business_access(allowed, db=session, user=seed_user)

    denied = route_request(
        "GET",
        f"/api/v1/organizations/{foreign.id}/reports/history",
        organization_id=foreign.id,
    )
    with pytest.raises(AuthorizationError):
        await require_business_access(denied, db=session, user=seed_user)
