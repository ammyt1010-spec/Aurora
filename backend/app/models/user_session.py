"""Persistent inventory of active device sessions per user in PostgreSQL.

Supports granular per-device session display and individual revocation while
minimizing personal data footprint.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PublicIdMixin
from app.models.types import BigIntPK


class UserSession(Base, PublicIdMixin):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Minimized Device & Network Info (privacy-preserving)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    device_family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    os_family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    browser_family: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Lifecycle Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
