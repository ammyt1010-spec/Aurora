"""Editable price bands and immutable per-report quote responses."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TariffInput(BaseModel):
    min_workers: int = Field(ge=1, le=10_000_000)
    max_workers: int | None = Field(default=None, ge=1, le=10_000_000)
    price: Decimal = Field(gt=0, decimal_places=2, max_digits=14)
    currency: Literal["PEN"] = "PEN"
    active: bool = True


class TariffRead(TariffInput):
    id: int
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class QuoteCreate(BaseModel):
    workers: int = Field(ge=1, le=10_000_000)


class OrderRead(BaseModel):
    id: int
    study_id: int
    organization_id: int
    workers: int
    tariff_min_workers: int
    tariff_max_workers: int | None
    tariff_id: int
    amount: Decimal
    currency: str
    status: str
    expires_at: datetime
    created_at: datetime
    paid_at: datetime | None
    payment_reference: str | None
    model_config = ConfigDict(from_attributes=True)


class PaymentConfirmation(BaseModel):
    payment_reference: str = Field(min_length=4, max_length=120, pattern=r"^[A-Za-z0-9_.:/# -]+$")
