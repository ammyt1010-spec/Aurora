"""Platform-managed tariffs and company report requests."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.billing import OrderRead, PaymentConfirmation, QuoteCreate, TariffInput, TariffRead
from app.services.billing_service import BillingService, is_platform_operator, require_operator

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/operator-status")
async def operator_status(user: User = Depends(get_current_user)):
    return {"is_operator": is_platform_operator(user)}


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
    return await BillingService(db).create_quote(study_id, payload.workers, user)


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
    from app.core.config import get_settings
    return {
        "enforced": get_settings().environment.lower() == "production",
        "model": "PAY_PER_REPORT",
        "basis": "WORKER_COUNT",
        "currency": "PEN",
        "payment_confirmation": "MANUAL_OPERATOR",
    }
