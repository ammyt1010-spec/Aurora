"""Versioned operator-reviewed headcount evidence (no documents or employee PII stored)."""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.types import BigIntPK


class HeadcountEvidence(Base):
    __tablename__ = "headcount_evidence"
    __table_args__ = (
        CheckConstraint("workers > 0", name="ck_headcount_evidence_workers_positive"),
        CheckConstraint("valid_until > verified_at", name="ck_headcount_evidence_validity"),
        UniqueConstraint("organization_id", "source_type", "document_sha256", name="uq_headcount_evidence_source_hash"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    workers: Mapped[int] = mapped_column(Integer, nullable=False)
    # Hash is for checking an externally retained, human-reviewed document.
    document_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    verified_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
