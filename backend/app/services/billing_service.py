"""Price per requested report, proportional only to a configured worker band.

A quote is immutable once issued. Company admins can request quotes, but
only the configured AURORA platform operator may edit tariffs or confirm payment.
No online payment integration or prices are assumed.
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationDomainError
from app.models.billing import ReportOrder, ReportTariff
from app.core.report_pricing import METHOD_LABELS, REFERENCE_WEB_TARIFFS
from app.models.instrument import Instrument, InstrumentVersion
from app.models.project import Project
from app.models.report import ReportRun
from app.models.study import Study
from app.models.user import OrganizationMembership, User
from app.schemas.billing import TariffInput
from app.services.audit_service import AuditService


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def is_platform_operator(user: User) -> bool:
    operator_id = get_settings().billing_operator_user_id
    return operator_id is not None and user.id == operator_id and user.status == "ACTIVE"


def require_operator(user: User) -> None:
    if not is_platform_operator(user):
        raise AuthorizationError("Sólo el administrador central de AURORA administra el tarifario y verifica pagos.")


class BillingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _tariff_lock(self) -> None:
        if self.db.bind is not None and self.db.bind.dialect.name == "postgresql":
            await self.db.execute(text("SELECT pg_advisory_xact_lock(847213001)"))

    async def list_tariffs(self, *, all_rows: bool = False) -> list[ReportTariff]:
        stmt = select(ReportTariff)
        if not all_rows:
            stmt = stmt.where(ReportTariff.active.is_(True))
        return list((await self.db.execute(stmt.order_by(ReportTariff.min_workers, ReportTariff.id))).scalars().all())

    async def save_tariff(self, payload: TariffInput, user: User, tariff_id: int | None = None) -> ReportTariff:
        require_operator(user)
        if payload.max_workers is not None and payload.max_workers < payload.min_workers:
            raise ValidationDomainError("El máximo de trabajadores no puede ser menor que el mínimo.")
        await self._tariff_lock()
        tariff = await self.db.get(ReportTariff, tariff_id) if tariff_id else None
        if tariff_id and tariff is None:
            raise NotFoundError("Tramo tarifario no encontrado.")
        # Reject overlapping enabled intervals, including open-ended tiers.
        if payload.active:
            for other in await self.list_tariffs():
                if other.method_code != payload.method_code:
                    continue
                if tariff is not None and other.id == tariff.id:
                    continue
                upper_a = payload.max_workers if payload.max_workers is not None else 10_000_000_001
                upper_b = other.max_workers if other.max_workers is not None else 10_000_000_001
                if payload.min_workers <= upper_b and other.min_workers <= upper_a:
                    raise ConflictError("El tramo se superpone con otra tarifa activa.")
        if tariff is None:
            tariff = ReportTariff(**payload.model_dump(), updated_by_user_id=user.id)
            self.db.add(tariff)
        else:
            for key, value in payload.model_dump().items():
                setattr(tariff, key, value)
            tariff.updated_by_user_id = user.id
            tariff.updated_at = datetime.now(UTC)
        await self.db.flush()
        await AuditService(self.db).log(
            action="REPORT_TARIFF_CHANGED", entity_type="report_tariff",
            entity_id=tariff.id, user_id=user.id,
            after_data={"method_code": tariff.method_code, "pricing_mode": tariff.pricing_mode,
                        "min_workers": tariff.min_workers, "max_workers": tariff.max_workers,
                        "price": str(tariff.price), "currency": tariff.currency, "active": tariff.active},
        )
        await self.db.commit()
        await self.db.refresh(tariff)
        return tariff

    async def _organization_admin(self, study_id: int, user: User):
        study = await self.db.get(Study, study_id)
        if study is None:
            raise NotFoundError("Estudio no encontrado.")
        project = await self.db.get(Project, study.project_id)
        if project is None or project.organization_id is None:
            raise ValidationDomainError("El estudio debe pertenecer a una empresa registrada.")
        member = await self.db.get(OrganizationMembership, (project.organization_id, user.id))
        if member is None or member.role_code not in {"OWNER", "ADMIN"}:
            raise AuthorizationError("Sólo un administrador de la empresa puede solicitar o revisar el informe.")
        return study, project

    async def _validate_method_for_study(self, study: Study, method_code: str) -> None:
        """Prevent buying a cheaper method than the version actually evaluated."""
        if study.instrument_version_id is None:
            if get_settings().environment.lower() == "production":
                raise ValidationDomainError("El estudio debe tener un instrumento versionado para cotizar.")
            return
        version = await self.db.get(InstrumentVersion, study.instrument_version_id)
        instrument = await self.db.get(Instrument, version.instrument_id) if version else None
        if instrument is None:
            raise ValidationDomainError("El instrumento del estudio no está disponible.")
        code = (instrument.code or "").upper()
        if code == "CENSOPAS_COPSOQ":
            kind = str((version.config or {}).get("censopas_version_kind") or version.version_code).upper()
            expected = "CENSOPAS_MEDIA" if kind in {"MEDIUM", "MEDIA"} else "CENSOPAS_CORTA" if kind in {"SHORT", "CORTA"} else None
        elif "SUSESO" in code or "ISTAS21" in code:
            expected = "SUSESO_ISTAS21_BREVE"
        else:
            raise ValidationDomainError("No existe un método tarifario autorizado para este instrumento.")
        if method_code != expected:
            raise ValidationDomainError("La metodología cotizada no corresponde al instrumento del estudio.")

    async def load_reference_tariffs(self, user: User) -> list[ReportTariff]:
        require_operator(user)
        await self._tariff_lock()
        # Never overwrite customer edits or previous sales.
        if await self.list_tariffs(all_rows=True):
            raise ConflictError("Hay tarifas registradas. Edita manualmente los tramos existentes.")
        for method, minimum, maximum, value in REFERENCE_WEB_TARIFFS:
            self.db.add(ReportTariff(
                method_code=method, pricing_mode="FIXED" if value is not None else "QUOTE",
                min_workers=minimum, max_workers=maximum,
                price=Decimal(value) if value is not None else None,
                currency="PEN", active=True, updated_by_user_id=user.id,
            ))
        await self.db.flush()
        await AuditService(self.db).log(
            action="REPORT_REFERENCE_TARIFF_LOADED", entity_type="report_tariff",
            entity_id=None, user_id=user.id,
            after_data={"count": len(REFERENCE_WEB_TARIFFS), "reference_discount_pct": 20, "channel": "WEB"},
        )
        await self.db.commit()
        return await self.list_tariffs()

    async def set_manual_quote_price(self, order_id: int, amount: Decimal, user: User) -> ReportOrder:
        require_operator(user)
        if amount <= 0:
            raise ValidationDomainError("El importe debe ser positivo.")
        order = (await self.db.execute(
            select(ReportOrder).where(ReportOrder.id == order_id).with_for_update()
        )).scalar_one_or_none()
        if order is None:
            raise NotFoundError("Solicitud de cotización no encontrada.")
        if order.status != "AWAITING_QUOTE" or order.pricing_mode != "QUOTE":
            raise ConflictError("Sólo las solicitudes Cotizar pendientes admiten un precio manual.")
        order.amount = amount
        order.status = "PENDING_PAYMENT"
        order.expires_at = datetime.now(UTC) + timedelta(days=7)
        await AuditService(self.db).log(
            action="REPORT_MANUAL_QUOTE_PRICED", entity_type="report_order",
            entity_id=order.id, user_id=user.id,
            after_data={"amount": str(amount), "currency": order.currency, "method": order.method_code},
        )
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def create_quote(self, study_id: int, workers: int, user: User, *,
                           method_code: str = "SUSESO_ISTAS21_BREVE") -> ReportOrder:
        if method_code not in METHOD_LABELS:
            raise ValidationDomainError("Metodología de informe desconocida.")
        if workers < 1:
            raise ValidationDomainError("La cantidad de trabajadores debe ser positiva.")
        study, project = await self._organization_admin(study_id, user)
        await self._validate_method_for_study(study, method_code)
        tariffs = [t for t in await self.list_tariffs()
                   if t.method_code == method_code and t.min_workers <= workers and (t.max_workers is None or workers <= t.max_workers)]
        if len(tariffs) != 1:
            raise ValidationDomainError("No existe un tramo tarifario válido para esta cantidad de trabajadores.")
        tariff = tariffs[0]
        order = ReportOrder(
            study_id=study_id, organization_id=project.organization_id,
            tariff_id=tariff.id, requested_by_user_id=user.id,
            method_code=method_code, pricing_mode=tariff.pricing_mode, workers=workers,
            tariff_min_workers=tariff.min_workers, tariff_max_workers=tariff.max_workers,
            amount=Decimal(tariff.price) if tariff.price is not None else None,
            currency=tariff.currency,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            status="PENDING_PAYMENT" if tariff.pricing_mode == "FIXED" else "AWAITING_QUOTE",
        )
        self.db.add(order)
        await self.db.flush()
        await AuditService(self.db).log(
            action="REPORT_QUOTE_CREATED", entity_type="report_order", entity_id=order.id,
            user_id=user.id, project_id=project.id,
            after_data={"workers": workers, "method_code": method_code,
                        "amount": str(order.amount) if order.amount is not None else None,
                        "currency": order.currency, "status": order.status},
        )
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def list_orders(self, study_id: int, user: User) -> list[ReportOrder]:
        await self._organization_admin(study_id, user)
        return list((await self.db.execute(
            select(ReportOrder).where(ReportOrder.study_id == study_id)
            .order_by(ReportOrder.created_at.desc(), ReportOrder.id.desc())
        )).scalars().all())

    async def pending_orders(self, user: User) -> list[ReportOrder]:
        require_operator(user)
        return list((await self.db.execute(
            select(ReportOrder).where(ReportOrder.status.in_(["PENDING_PAYMENT", "AWAITING_QUOTE"]))
            .order_by(ReportOrder.created_at, ReportOrder.id)
        )).scalars().all())

    async def confirm_payment(self, order_id: int, payment_reference: str, user: User) -> ReportOrder:
        require_operator(user)
        order = (await self.db.execute(
            select(ReportOrder).where(ReportOrder.id == order_id).with_for_update()
        )).scalar_one_or_none()
        if order is None:
            raise NotFoundError("Cotización no encontrada.")
        if order.status != "PENDING_PAYMENT" or order.amount is None:
            raise ConflictError("Primero debe existir un importe confirmado de cotización.")
        if _utc(order.expires_at) <= datetime.now(UTC):
            raise ConflictError("La cotización venció; genera una nueva con el tarifario vigente.")
        # Manual verification is external. This endpoint records authorization
        # by a trusted operator, not an independently verified bank transfer.
        order.payment_reference = payment_reference
        order.confirmed_by_user_id = user.id
        order.paid_at = datetime.now(UTC)
        order.status = "PAID"
        study = await self.db.get(Study, order.study_id)
        await AuditService(self.db).log(
            action="REPORT_PAYMENT_CONFIRMED", entity_type="report_order",
            entity_id=order.id, user_id=user.id,
            project_id=study.project_id if study else None,
            after_data={"reference": payment_reference, "amount": str(order.amount)},
        )
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def reserve_report_order(self, order_id: int | None, study_id: int) -> ReportOrder | None:
        """Hold row lock until report commit. A paid order can fund one report run."""
        if get_settings().environment.lower() != "production":
            if order_id is None:
                return None   # legacy test/dev flows remain available.
        if order_id is None:
            raise ConflictError("Antes de generar el informe, solicita una cotización y confirma su pago.")
        order = (await self.db.execute(
            select(ReportOrder).where(ReportOrder.id == order_id).with_for_update()
        )).scalar_one_or_none()
        if order is None or order.study_id != study_id:
            raise AuthorizationError("La orden no corresponde al estudio.")
        if order.status != "PAID":
            raise ConflictError("La orden no tiene un pago confirmado o ya fue utilizada.")
        previous = (await self.db.execute(
            select(ReportRun.id).where(ReportRun.billing_order_id == order.id)
        )).scalar_one_or_none()
        if previous is not None:
            raise ConflictError("Esta orden ya fue utilizada para generar un informe.")
        return order

    async def consume_order(self, order: ReportOrder | None, report_id: int) -> None:
        if order is None:
            return
        order.status = "CONSUMED"
        order.consumed_at = datetime.now(UTC)
        await AuditService(self.db).log(
            action="REPORT_ORDER_CONSUMED", entity_type="report_order", entity_id=order.id,
            project_id=(await self.db.get(Study, order.study_id)).project_id,
            after_data={"report_id": report_id},
        )
