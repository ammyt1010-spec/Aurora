"""Editable price bands and immutable per-report quote responses."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


MethodCode = Literal["SUSESO_ISTAS21_BREVE", "CENSOPAS_CORTA", "CENSOPAS_MEDIA"]


class TariffInput(BaseModel):
    method_code: MethodCode = "SUSESO_ISTAS21_BREVE"
    pricing_mode: Literal["FIXED", "QUOTE"] = "FIXED"
    min_workers: int = Field(ge=1, le=10_000_000)
    max_workers: int | None = Field(default=None, ge=1, le=10_000_000)
    price: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=14)
    currency: Literal["PEN"] = "PEN"
    active: bool = True

    @model_validator(mode="after")
    def validate_pricing(self):
        if self.max_workers is not None and self.max_workers < self.min_workers:
            raise ValueError("El máximo debe ser mayor o igual al mínimo.")
        if self.pricing_mode == "FIXED" and self.price is None:
            raise ValueError("El precio fijo es obligatorio.")
        if self.pricing_mode == "QUOTE" and self.price is not None:
            raise ValueError("Un tramo Cotizar no puede tener un precio fijo.")
        return self


class TariffRead(TariffInput):
    id: int
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class QuoteCreate(BaseModel):
    workers: int = Field(ge=1, le=10_000_000)
    method_code: MethodCode = "SUSESO_ISTAS21_BREVE"


class OrderRead(BaseModel):
    id: int
    study_id: int
    organization_id: int
    workers: int
    method_code: MethodCode
    pricing_mode: Literal["FIXED", "QUOTE"]
    tariff_min_workers: int
    tariff_max_workers: int | None
    tariff_id: int
    amount: Decimal | None
    currency: str
    status: str
    expires_at: datetime
    created_at: datetime
    paid_at: datetime | None
    payment_reference: str | None
    model_config = ConfigDict(from_attributes=True)


class PaymentConfirmation(BaseModel):
    payment_reference: str = Field(min_length=4, max_length=120, pattern=r"^[A-Za-z0-9_.:/# -]+$")


class ManualQuotePrice(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
