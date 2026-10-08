import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.types import BigIntPK, JSONVariant


class ReportTemplate(Base, TimestampMixin):
    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
    )
    code: Mapped[str | None] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(80), nullable=False)
    instrument_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("instrument_versions.id")
    )
    template_config: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")


class ReportRun(Base):
    __tablename__ = "report_runs"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
    )
    billing_order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("report_orders.id"), unique=True)
    study_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("studies.id", ondelete="CASCADE"), nullable=False
    )
    report_template_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("report_templates.id")
    )
    requested_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    analysis_run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("analysis_runs.id"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    output_format: Mapped[str] = mapped_column(String(30), nullable=False, default="JSON")
    storage_path: Mapped[str | None] = mapped_column(Text)
    data_hash: Mapped[str | None] = mapped_column(String(64))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONVariant, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
