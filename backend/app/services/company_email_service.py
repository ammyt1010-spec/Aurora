"""Short-lived, single-purpose email confirmation for public company accounts."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from html import escape
import time
from urllib.parse import quote

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ColmenaDomainError
from app.models.user import User
from app.services.audit_service import AuditService


class EmailDeliveryError(ColmenaDomainError):
    http_status = 503
    error_code = "EMAIL_DELIVERY_UNAVAILABLE"


def confirmation_token(user: User) -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": str(user.id), "email": user.email, "sv": user.session_version,
            "scope": "company:verify-email",
            "exp": datetime.now(UTC) + timedelta(hours=24),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _send_email(recipient: str, company_name: str, token: str) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        raise EmailDeliveryError("El correo de confirmación no está configurado.")
    link = f"{settings.public_app_url.rstrip('/')}/verify-email?token={quote(token)}"
    safe_company = escape(company_name)
    payload = {
        "from": settings.email_from,
        "to": [recipient],
        "subject": "Confirma tu cuenta empresarial en AURORA",
        "html": (
            '<!doctype html><html lang="es"><head><meta charset="utf-8">'
            '<title>Confirma tu cuenta AURORA</title></head><body style="font-family:Arial,sans-serif;'
            'color:#183047;background:#f5f9fc;padding:24px">'
            '<main style="max-width:560px;margin:auto;background:#fff;border-radius:18px;padding:30px">'
            '<h1 style="font-size:24px">Confirma tu cuenta AURORA</h1>'
            f"<p>Hola, {safe_company}.</p>"
            "<p>Confirma tu correo para activar tu cuenta empresarial y tus cuatro evaluaciones gratuitas.</p>"
            f'<p><a href="{escape(link, quote=True)}" style="display:inline-block;background:#087d9b;'
            'color:#fff;padding:14px 22px;border-radius:9px;text-decoration:none">Confirmar mi cuenta</a></p>'
            "<p>El enlace vence en 24 horas. Si no solicitaste la cuenta, ignora este mensaje.</p>"
            '</main></body></html>'
        ),
        "text": (
            f"Hola, {company_name}. Confirma tu correo para activar AURORA y tus cuatro evaluaciones gratuitas: "
            f"{link} El enlace vence en 24 horas. Si no solicitaste la cuenta, ignora este mensaje."
        ),
    }
    event_key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    for attempt in range(3):
        try:
            response = httpx.post(
                "https://api.resend.com/emails", json=payload,
                headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Idempotency-Key": f"aurora-verify-{event_key}",
                }, timeout=10,
            )
            if response.status_code in (200, 201, 202):
                return
            if response.status_code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise EmailDeliveryError("No se pudo enviar el correo de confirmación. Inténtalo de nuevo.")
        except httpx.RequestError as exc:
            if attempt == 2:
                raise EmailDeliveryError("No se pudo enviar el correo de confirmación. Inténtalo de nuevo.") from exc
        time.sleep(0.5 * (2 ** attempt))


async def send_confirmation(user: User, company_name: str) -> None:
    await asyncio.to_thread(_send_email, user.email or "", company_name, confirmation_token(user))


async def verify_company_email(session: AsyncSession, token: str) -> None:
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], options={"require": ["exp"]})
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
        raise AuthenticationError("El enlace de confirmación es inválido o expiró.") from exc
    if claims.get("scope") != "company:verify-email" or user_id <= 0:
        raise AuthenticationError("El enlace de confirmación es inválido o expiró.")
    user = await session.get(User, user_id)
    if (
        user is None or user.status != "PENDING_EMAIL"
        or user.email != claims.get("email") or user.session_version != claims.get("sv")
        or user.managed_company_id is None
    ):
        raise AuthenticationError("El enlace de confirmación ya no es válido.")
    user.status = "ACTIVE"
    await AuditService(session).log(
        action="COMPANY_EMAIL_VERIFIED", entity_type="user", entity_id=user.id,
        user_id=user.id, organization_id=user.managed_company_id,
    )
    await session.commit()


async def resend_confirmation(session: AsyncSession, email: str) -> None:
    # A neutral response at the API layer avoids revealing registered addresses.
    user = await session.scalar(select(User).where(User.email == email.strip().lower()).with_for_update())
    if user is None or user.status != "PENDING_EMAIL" or user.managed_company_id is None:
        return
    now = datetime.now(UTC)
    recent = []
    for value in (user.metadata_ or {}).get("email_verification_sent_at", []):
        try:
            sent_at = datetime.fromisoformat(value)
            if sent_at.tzinfo and now - sent_at < timedelta(hours=1):
                recent.append(sent_at)
        except (TypeError, ValueError):
            continue
    if len(recent) >= 3 or (recent and now - max(recent) < timedelta(seconds=60)):
        return
    from app.models.user import Organization

    company = await session.get(Organization, user.managed_company_id)
    if company is not None:
        await send_confirmation(user, company.legal_name or company.name)
        user.metadata_ = {
            **(user.metadata_ or {}),
            "email_verification_sent_at": [item.isoformat() for item in recent] + [now.isoformat()],
        }
        await session.commit()
