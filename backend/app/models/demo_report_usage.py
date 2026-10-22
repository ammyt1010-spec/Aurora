"""Consumo único de muestra demo por cuenta empresarial habilitada."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DemoReportUsage(Base):
    __tablename__ = "demo_report_usages"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(22), nullable=False, default="RESERVED")
    report_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("report_runs.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
