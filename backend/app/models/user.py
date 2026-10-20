from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PublicIdMixin, TimestampMixin
from app.models.types import BigIntPK, JSONVariant


class User(Base, PublicIdMixin, TimestampMixin):
    """Espejo mínimo de `colmena.users`. Reutilizada por todo el resto (harness §67.3)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    username: Mapped[str | None] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String)
    first_name: Mapped[str | None] = mapped_column(String(150))
    last_name: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONVariant, nullable=False, default=dict
    )


class Organization(Base, PublicIdMixin, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    tax_id: Mapped[str | None] = mapped_column(String(80))
    organization_type: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    free_report_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    free_report_project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="SET NULL")
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONVariant, nullable=False, default=dict
    )


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"

    organization_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_code: Mapped[str] = mapped_column(String(60), nullable=False)
    permissions: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
