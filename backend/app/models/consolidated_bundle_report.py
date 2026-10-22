"""Informe consolidado de batería con hash de cada informe fuente."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PublicIdMixin
from app.models.types import BigIntPK, JSONVariant


class ConsolidatedBundleReport(Base, PublicIdMixin):
    __tablename__ = "consolidated_bundle_reports"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    bundle_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("evaluation_bundles.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
