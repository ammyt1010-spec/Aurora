"""Editable price bands and immutable per-report quote responses."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# MethodCode base para compatibilidad y extensibilidad multidisciplinaria (PR #13)
MethodCode = str
HeadcountSource = Literal["ESTUDIO_DECLARADO", "PLANILLA_OFICIAL_EMPRESA", "AUDITORIA_RRHH"]


class TariffInput(BaseModel):
    instrument_id: int | None = None
    method_code: str = Field(default="SUSESO_ISTAS21_BREVE", min_length=2, max_length=50)
    pricing_mode: Literal["FIXED", "QUOTE"] = "FIXED"
    min_workers: int = Field(ge=1, le=10_000_000)
    max_workers: int | None = Field(default=None, ge=1, le=10_000_000)
    price: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=14)
    currency: Literal["PEN"] = "PEN"
    notes: str | None = None
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
    method_code: str = "SUSESO_ISTAS21_BREVE"
    headcount_source: HeadcountSource | None = None


class OrderRead(BaseModel):
    id: int
    study_id: int
    organization_id: int
    workers: int
    headcount_source: str = "ESTUDIO_DECLARADO"
    snapshot_data: dict | None = None
    method_code: str
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


class EnterpriseBillingSummary(BaseModel):
    organization_id: int
    organization_name: str
    total_orders: int
    available_licenses: int
    consumed_licenses: int
    pending_payment: int
    awaiting_quote: int
    orders: list[OrderRead]
