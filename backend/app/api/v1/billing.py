"""Platform-managed tariffs and company report requests."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.billing import EnterpriseBillingSummary, ManualQuotePrice, OrderRead, PaymentConfirmation, QuoteCreate, TariffInput, TariffRead
from app.services.billing_service import BillingService, is_platform_operator

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/operator-status")
async def operator_status(user: User = Depends(get_current_user)):
    return {"is_operator": is_platform_operator(user)}


@router.get("/payment-instructions")
async def payment_instructions(_user: User = Depends(get_current_user)):
    from app.core.config import get_settings
    settings = get_settings()
    payment_fields = (
        settings.payment_bank_name, settings.payment_account_holder,
        settings.payment_account_number, settings.payment_cci,
    )
    provisional = any(
        not value.strip() or any(marker in value.lower() for marker in ("pendiente", "por definir", "provisional"))
        for value in payment_fields
    )
    return {
        "bank_name": settings.payment_bank_name,
        "account_holder": settings.payment_account_holder,
        "account_number": settings.payment_account_number,
        "cci": settings.payment_cci,
        "provisional": provisional,
        "notice": (
            "Datos provisionales: no realices una transferencia hasta que AURORA confirme la cuenta definitiva."
            if provisional else
            "Incluye el número de orden en la referencia. La activación requiere confirmación manual del operador."
        ),
    }


@router.get("/methods")
async def list_methods(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """Metodologías autorizadas para cotización y licenciamiento."""
    from app.core.report_pricing import METHOD_LABELS, get_method_label
    from app.models.billing import ReportTariff
    from sqlalchemy import select

    tariff_methods = (await db.execute(select(ReportTariff.method_code).where(ReportTariff.active.is_(True)).distinct())).scalars().all()
    all_methods = dict(METHOD_LABELS)
    for m in tariff_methods:
        if m not in all_methods:
            all_methods[m] = get_method_label(m)
    return [{"code": k, "label": v} for k, v in all_methods.items()]


@router.get("/tariffs", response_model=list[TariffRead])
async def list_tariffs(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    return await BillingService(db).list_tariffs()


@router.post("/tariffs", response_model=TariffRead, status_code=201)
async def create_tariff(
    payload: TariffInput, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    return await BillingService(db).save_tariff(payload, user)


@router.put("/tariffs/{tariff_id}", response_model=TariffRead)
async def update_tariff(
    tariff_id: int, payload: TariffInput, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await BillingService(db).save_tariff(payload, user, tariff_id=tariff_id)


@router.post("/studies/{study_id}/quotes", response_model=OrderRead, status_code=201)
async def create_quote(
    study_id: int, payload: QuoteCreate, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await BillingService(db).create_quote(
        study_id, payload.workers, user,
        method_code=payload.method_code,
        headcount_source=payload.headcount_source,
    )


@router.get("/studies/{study_id}/orders", response_model=list[OrderRead])
async def list_orders(
    study_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    return await BillingService(db).list_orders(study_id, user)


@router.get("/pending-orders", response_model=list[OrderRead])
async def pending_orders(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await BillingService(db).pending_orders(user)


@router.post("/orders/{order_id}/confirm-payment", response_model=OrderRead)
async def confirm_payment(
    order_id: int, payload: PaymentConfirmation, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await BillingService(db).confirm_payment(order_id, payload.payment_reference, user)


@router.get("/policy")
async def billing_policy(_user: User = Depends(get_current_user)):
    return {
        "enforced": True,  # Never authorized merely for being localhost.
        "model": "FOUR_FREE_EVALUATIONS_THEN_PAY_PER_EVALUATION",
        "free_evaluation_limit": 4,
        "reports_per_evaluation": 1,
        "basis": "WORKER_COUNT",
        "currency": "PEN",
        "payment_confirmation": "MANUAL_OPERATOR",
    }


@router.post("/tariffs/load-reference", response_model=list[TariffRead])
async def load_reference_rates(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Explicitly apply the screenshot-based web tariff; only platform operator."""
    return await BillingService(db).load_reference_tariffs(user)


@router.post("/orders/{order_id}/set-manual-price", response_model=OrderRead)
async def set_manual_quote(
    order_id: int, payload: ManualQuotePrice, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await BillingService(db).set_manual_quote_price(order_id, payload.amount, user)


@router.get("/organizations/{organization_id}/summary", response_model=EnterpriseBillingSummary)
async def organization_billing_summary(
    organization_id: int, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await BillingService(db).get_organization_billing_summary(organization_id, user)


@router.get("/organizations/{organization_id}/orders", response_model=list[OrderRead])
async def organization_orders(
    organization_id: int, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    summary = await BillingService(db).get_organization_billing_summary(organization_id, user)
    return summary["orders"]

