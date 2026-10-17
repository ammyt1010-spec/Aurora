"""Price per requested report, proportional only to a configured worker band.

A quote is immutable once issued. Company admins can request quotes, but
only the configured AURORA platform operator may edit tariffs or confirm payment.
No online payment integration or prices are assumed.
"""
import re
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
from app.models.user import Organization, OrganizationMembership, User
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
        org = await self.db.get(Organization, project.organization_id)
        member = await self.db.get(OrganizationMembership, (project.organization_id, user.id))
        if member is None or member.role_code not in {"OWNER", "ADMIN"}:
            raise AuthorizationError("Sólo un administrador de la empresa puede solicitar o revisar el informe.")
        return study, project, org

    async def _validate_method_for_study(self, study: Study, method_code: str) -> None:
        """Prevent buying a cheaper method than the version actually evaluated,
        and verify that the instrument is authorized and configured methodologically."""
        if study.instrument_version_id is None:
            if get_settings().environment.lower() == "production":
                raise ValidationDomainError("El estudio debe tener un instrumento versionado para cotizar.")
            return
        version = await self.db.get(InstrumentVersion, study.instrument_version_id)
        instrument = await self.db.get(Instrument, version.instrument_id) if version else None
        if instrument is None:
            raise ValidationDomainError("El instrumento del estudio no está disponible.")

        # 1. Rechaza instrumentos no autorizados
        if not instrument.is_system and getattr(instrument, "status", "DRAFT") not in {"AUTHORIZED", "ACTIVE"}:
            raise ValidationDomainError("El instrumento seleccionado no cuenta con autorización corporativa para emisión de informes.")

        # 2. Rechaza instrumentos que carezcan de configuración metodológica completa
        scoring_status = getattr(version, "scoring_status", "NOT_CONFIGURED")
        censopas_kind = (version.config or {}).get("censopas_version_kind")
        if scoring_status != "CONFIGURED" and not censopas_kind:
            raise ValidationDomainError("El instrumento carece de configuración psicométrica/metodológica suficiente (scoring_status=CONFIGURED) para ser evaluado.")

        # 3. Resolución desacoplada de la metodología esperada
        code = (instrument.code or "").upper()
        expected = None
        if getattr(instrument, "method_code", None):
            expected = instrument.method_code
        elif (version.config or {}).get("method_code"):
            expected = version.config["method_code"]
        elif code == "CENSOPAS_COPSOQ":
            kind = str(censopas_kind or version.version_code).upper()
            expected = "CENSOPAS_MEDIA" if kind in {"MEDIUM", "MEDIA"} else "CENSOPAS_CORTA" if kind in {"SHORT", "CORTA"} else None
        elif "SUSESO" in code or "ISTAS21" in code:
            expected = "SUSESO_ISTAS21_BREVE"
        elif instrument.code:
            expected = instrument.code
        else:
            raise ValidationDomainError("No existe un método tarifario autorizado para este instrumento.")

        if method_code != expected:
            raise ValidationDomainError("La metodología cotizada no corresponde al instrumento del estudio.")

        # 4. Verificar que exista un tramo tarifario activo para el método
        tariff_exists = (await self.db.execute(
            select(ReportTariff.id).where(ReportTariff.method_code == expected, ReportTariff.active.is_(True)).limit(1)
        )).scalar()
        if not tariff_exists:
            raise ValidationDomainError(f"No existe un tarifario activo autorizado por el operador para el método '{expected}'.")

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
        if order.snapshot_data is not None:
            # Reassign JSON rather than mutating in place: SQLAlchemy's JSON
            # column does not track nested dict changes automatically.
            order.snapshot_data = {
                **order.snapshot_data,
                "amount": str(amount),
                "pricing_finalized_at": datetime.now(UTC).isoformat(),
            }
        await AuditService(self.db).log(
            action="REPORT_MANUAL_QUOTE_PRICED", entity_type="report_order",
            entity_id=order.id, user_id=user.id,
            after_data={"amount": str(amount), "currency": order.currency, "method": order.method_code},
        )
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def create_quote(
        self, study_id: int, workers: int, user: User, *,
        method_code: str = "SUSESO_ISTAS21_BREVE",
        headcount_source: str | None = None,
    ) -> ReportOrder:
        is_known = method_code in METHOD_LABELS
        if not is_known:
            has_tariff = bool((await self.db.execute(
                select(ReportTariff.id).where(ReportTariff.method_code == method_code, ReportTariff.active.is_(True)).limit(1)
            )).scalar())
            if not has_tariff:
                raise ValidationDomainError("Metodología de informe desconocida.")
        if workers < 1:
            raise ValidationDomainError("La cantidad de trabajadores debe ser positiva.")
        study, project, org = await self._organization_admin(study_id, user)
        await self._validate_method_for_study(study, method_code)

        # 1. Definir fuente empresarial verificable y evitar reducciones unilaterales (Req 2 y 3)
        allowed_sources = {"ESTUDIO_DECLARADO", "PLANILLA_OFICIAL_EMPRESA", "AUDITORIA_RRHH"}
        if headcount_source is not None and headcount_source not in allowed_sources:
            raise ValidationDomainError("La fuente de dotación declarada no está reconocida.")

        metadata = (org.metadata_ or {}) if org else {}
        # The user cannot self-certify an official evidence source by changing
        # a label sent in the quote request. These fields are populated only
        # by a separate verified enterprise-operator workflow.
        try:
            verified_workers = int(metadata["verified_workers"]) if metadata.get("verified_workers") is not None else None
            audited_workers = int(metadata["rrhh_verified_workers"]) if metadata.get("rrhh_verified_workers") is not None else None
            company_workers = int(metadata["headcount"]) if metadata.get("headcount") is not None else None
        except (TypeError, ValueError) as exc:
            raise ValidationDomainError("La dotación registrada de la empresa es inválida.") from exc
        for value in (verified_workers, audited_workers, company_workers):
            if value is not None and value < 1:
                raise ValidationDomainError("La dotación registrada debe ser positiva.")
        if headcount_source == "PLANILLA_OFICIAL_EMPRESA" and verified_workers is None:
            raise ValidationDomainError("No existe una planilla oficial verificada para esta empresa.")
        if headcount_source == "AUDITORIA_RRHH" and audited_workers is None:
            raise ValidationDomainError("No existe una auditoría de RR. HH. verificada para esta empresa.")

        resolved_source = headcount_source or (
            "PLANILLA_OFICIAL_EMPRESA" if verified_workers is not None else "ESTUDIO_DECLARADO"
        )
        verified_floor = max(
            (n for n in (verified_workers, audited_workers, company_workers) if n is not None),
            default=None,
        )
        if verified_floor is not None and workers < verified_floor:
            raise ValidationDomainError(
                f"La cantidad de trabajadores ({workers}) no puede ser menor a la dotación oficial "
                f"registrada de la empresa ({verified_floor})."
            )

        study_settings = dict(study.settings or {})
        study_hc = study_settings.get("headcount") or study_settings.get("declared_workers")
        if study_hc is not None and workers < int(study_hc):
            raise ValidationDomainError(
                f"La cantidad de trabajadores ({workers}) no puede ser menor a la dotación "
                f"declarada previamente para este estudio ({study_hc})."
            )

        if "headcount" not in study_settings:
            study_settings["headcount"] = workers
            study_settings["headcount_source"] = resolved_source
            study_settings["headcount_version"] = 1
            study.settings = study_settings
            await self.db.flush()

        # Resolver instrumento del estudio para vinculación estricta de tarifas
        current_instrument_id = None
        if study.instrument_version_id:
            version = await self.db.get(InstrumentVersion, study.instrument_version_id)
            if version:
                current_instrument_id = version.instrument_id

        all_tariffs = await self.list_tariffs()
        matching_tariffs = [
            t for t in all_tariffs
            if t.method_code == method_code
            and t.min_workers <= workers
            and (t.max_workers is None or workers <= t.max_workers)
        ]

        # Evita utilizar una tarifa vinculada a otro instrumento aunque coincida el código metodológico
        compatible_tariffs = [
            t for t in matching_tariffs
            if t.instrument_id is None or (current_instrument_id is not None and t.instrument_id == current_instrument_id)
        ]

        # Si existen tarifas específicamente asignadas a este instrumento, tienen prioridad estricta
        specific_tariffs = [
            t for t in compatible_tariffs
            if t.instrument_id == current_instrument_id and current_instrument_id is not None
        ]
        candidates = specific_tariffs if specific_tariffs else [t for t in compatible_tariffs if t.instrument_id is None]

        if len(candidates) != 1:
            if any(t.instrument_id is not None and t.instrument_id != current_instrument_id for t in matching_tariffs):
                raise ValidationDomainError(
                    "La tarifa existente para esta metodología pertenece a otro instrumento específico y no puede ser utilizada."
                )
            raise ValidationDomainError("No existe un tramo tarifario válido para esta cantidad de trabajadores e instrumento.")
        tariff = candidates[0]

        # 2. Fotografía inmutable de tarifa, metodología, empresa, estudio, trabajadores e importe (Req 4)
        snapshot = {
            "version": 1,
            "tariff": {
                "id": tariff.id,
                "method_code": tariff.method_code,
                "instrument_id": tariff.instrument_id,
                "pricing_mode": tariff.pricing_mode,
                "min_workers": tariff.min_workers,
                "max_workers": tariff.max_workers,
                "price": str(tariff.price) if tariff.price is not None else None,
                "currency": tariff.currency,
            },
            "instrument": {
                "id": current_instrument_id,
                "version_id": study.instrument_version_id,
            },
            "method": {
                "code": method_code,
                "label": METHOD_LABELS.get(method_code, method_code),
            },
            "organization": {
                "id": project.organization_id,
                "name": org.name if org else None,
                "tax_id": org.tax_id if org else None,
            },
            "study": {
                "id": study.id,
                "name": study.name,
            },
            "workers": workers,
            "headcount_source": resolved_source,
            "amount": str(tariff.price) if tariff.price is not None else None,
            "currency": tariff.currency,
            "created_at": datetime.now(UTC).isoformat(),
        }

        order = ReportOrder(
            study_id=study_id, organization_id=project.organization_id,
            tariff_id=tariff.id, requested_by_user_id=user.id,
            method_code=method_code, pricing_mode=tariff.pricing_mode, workers=workers,
            headcount_source=resolved_source, snapshot_data=snapshot,
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
                        "headcount_source": resolved_source,
                        "amount": str(order.amount) if order.amount is not None else None,
                        "currency": order.currency, "status": order.status},
        )
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def list_orders(self, study_id: int, user: User) -> list[ReportOrder]:
        study, project, _ = await self._organization_admin(study_id, user)
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
        if order.status == "PAID":
            raise ConflictError("Esta orden ya fue pagada.")
        if order.status != "PENDING_PAYMENT" or order.amount is None:
            raise ConflictError("Primero debe existir un importe confirmado de cotización.")
        if _utc(order.expires_at) <= datetime.now(UTC):
            raise ConflictError("La cotización venció; genera una nueva con el tarifario vigente.")

        # Sanitizar referencia de pago para no almacenar secretos financieros (Req 10)
        sanitized_reference = re.sub(r"\b(?:\d[ -]*?){13,19}\b", "[REDACTED_CARD]", payment_reference.strip())
        order.payment_reference = sanitized_reference
        order.confirmed_by_user_id = user.id
        order.paid_at = datetime.now(UTC)
        order.status = "PAID"
        study = await self.db.get(Study, order.study_id)
        await AuditService(self.db).log(
            action="REPORT_PAYMENT_CONFIRMED", entity_type="report_order",
            entity_id=order.id, user_id=user.id,
            project_id=study.project_id if study else None,
            after_data={"reference": sanitized_reference, "amount": str(order.amount), "workers": order.workers},
        )
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def reserve_report_order(self, order_id: int | None, study_id: int, request=None) -> ReportOrder | None:
        """Hold row lock until report commit. Atomically transition to RESERVED to prevent concurrent reuse."""
        from app.core.synthetic_test_bypass import is_authorized_synthetic_test
        if not is_authorized_synthetic_test(request) and order_id is None:
            raise ConflictError(
                "Antes de generar el informe en una instancia comercial o pública, "
                "solicita una cotización y confirma su pago."
            )
        if order_id is None:
            return None

        order = (await self.db.execute(
            select(ReportOrder).where(ReportOrder.id == order_id).with_for_update()
        )).scalar_one_or_none()
        if order is None or order.study_id != study_id:
            raise AuthorizationError("La orden no corresponde al estudio.")
        if order.status == "RESERVED":
            raise ConflictError("La orden ya se encuentra reservada por otra solicitud en curso.")
        if order.status == "CONSUMED":
            raise ConflictError("Esta orden ya fue utilizada para generar un informe.")
        if order.status != "PAID":
            raise ConflictError(f"La orden no tiene un pago confirmado o no está disponible (estado actual: {order.status}).")
        if _utc(order.expires_at) <= datetime.now(UTC):
            raise ConflictError("La orden pagada ha vencido su período de vigencia.")

        previous = (await self.db.execute(
            select(ReportRun.id).where(ReportRun.billing_order_id == order.id)
        )).scalar_one_or_none()
        if previous is not None:
            raise ConflictError("Esta orden ya fue utilizada para generar un informe.")

        # Transición atómica a RESERVED bajo bloqueo de fila (Req 5)
        order.status = "RESERVED"
        await self.db.flush()
        return order

    async def release_reservation(self, order: ReportOrder | None) -> None:
        """If report generation fails, safely roll back reservation so credit is not lost (Req 9)."""
        if order is None:
            return
        order.status = "PAID"
        order.consumed_at = None
        await self.db.flush()

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

    async def get_organization_billing_summary(self, organization_id: int, user: User) -> dict:
        """Consolidado empresarial de licencias y órdenes (Req 11)."""
        if not is_platform_operator(user):
            member = await self.db.get(OrganizationMembership, (organization_id, user.id))
            if member is None or member.role_code not in {"OWNER", "ADMIN"}:
                raise AuthorizationError("Sólo administradores de la empresa pueden consultar el estado comercial.")
        org = await self.db.get(Organization, organization_id)
        if org is None:
            raise NotFoundError("Empresa no encontrada.")

        orders = list((await self.db.execute(
            select(ReportOrder).where(ReportOrder.organization_id == organization_id)
            .order_by(ReportOrder.created_at.desc(), ReportOrder.id.desc())
        )).scalars().all())

        # An expired paid order is not a spendable license. Keep its persisted
        # audit status unchanged; expose EXPIRED in the dashboard view only.
        from app.schemas.billing import OrderRead
        now = datetime.now(UTC)
        available = sum(1 for o in orders if o.status == "PAID" and _utc(o.expires_at) > now)
        view_orders = [
            OrderRead.model_validate(o).model_copy(update={"status": "EXPIRED"})
            if o.status == "PAID" and _utc(o.expires_at) <= now
            else OrderRead.model_validate(o)
            for o in orders
        ]
        consumed = sum(1 for o in orders if o.status == "CONSUMED")
        pending = sum(1 for o in orders if o.status == "PENDING_PAYMENT")
        awaiting = sum(1 for o in orders if o.status == "AWAITING_QUOTE")

        return {
            "organization_id": org.id,
            "organization_name": org.name,
            "total_orders": len(orders),
            "available_licenses": available,
            "consumed_licenses": consumed,
            "pending_payment": pending,
            "awaiting_quote": awaiting,
            "orders": view_orders,
        }

