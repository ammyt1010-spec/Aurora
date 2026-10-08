"""Pay-per-report commercial model. Each quote snapshots the approved tariff."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import BigIntPK


class ReportTariff(Base):
    __tablename__ = "report_tariffs"
    __table_args__ = (
        CheckConstraint("min_workers > 0", name="ck_tariff_min_positive"),
        CheckConstraint("max_workers IS NULL OR max_workers >= min_workers", name="ck_tariff_range"),
        CheckConstraint("price IS NULL OR price >= 0", name="ck_tariff_price_nonnegative"),
        CheckConstraint("(pricing_mode = 'QUOTE' AND price IS NULL) OR (pricing_mode = 'FIXED' AND price > 0)", name="ck_tariff_mode_price"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    method_code: Mapped[str] = mapped_column(String(50), nullable=False, default="SUSESO_ISTAS21_BREVE")
    pricing_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="FIXED")
    min_workers: Mapped[int] = mapped_column(Integer, nullable=False)
    max_workers: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PEN")
    active: Mapped[bool] = mapped_column(nullable=False, default=True)
    updated_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReportOrder(Base):
    __tablename__ = "report_orders"
    __table_args__ = (
        CheckConstraint("workers > 0", name="ck_order_workers_positive"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="ck_order_amount_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    study_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False)
    tariff_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("report_tariffs.id"), nullable=False)
    requested_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    method_code: Mapped[str] = mapped_column(String(50), nullable=False, default="SUSESO_ISTAS21_BREVE")
    pricing_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="FIXED")
    workers: Mapped[int] = mapped_column(Integer, nullable=False)
    tariff_min_workers: Mapped[int] = mapped_column(Integer, nullable=False)
    tariff_max_workers: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="PEN")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_PAYMENT")
    payment_reference: Mapped[str | None] = mapped_column(String(120))
    confirmed_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
