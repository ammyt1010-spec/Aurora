"""Acceso comercial a una evaluación creada desde Inicio."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import BigIntPK


class EvaluationEntitlement(Base):
    __tablename__ = "evaluation_entitlements"
    __table_args__ = (
        CheckConstraint("access_kind IN ('FREE', 'PAID')", name="ck_evaluation_access_kind"),
        CheckConstraint("status IN ('ACTIVE', 'PENDING_PAYMENT')", name="ck_evaluation_access_status"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    study_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("studies.id", ondelete="CASCADE"), nullable=False, unique=True)
    access_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("report_orders.id", ondelete="SET NULL"), unique=True)
    free_report_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("report_runs.id", ondelete="SET NULL"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
