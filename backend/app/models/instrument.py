import datetime as dt

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PublicIdMixin, TimestampMixin
from app.models.types import BigIntPK, JSONVariant

# Disciplinas soportadas para la arquitectura multidisciplinaria (PR #13)
INSTRUMENT_DISCIPLINES = (
    "PSICOSOCIAL",
    "ERGONOMIA",
    "CLIMA_ORGANIZACIONAL",
    "SEGURIDAD_SALUD",
    "LIDERAZGO_BURNOUT",
    "OTRO",
)

# Estados del instrumento en catálogo empresarial
INSTRUMENT_STATUSES = ("DRAFT", "VALIDATING", "AUTHORIZED", "ACTIVE", "LOCKED", "ARCHIVED")

# Estados válidos de instrument_version (harness §42): DRAFT, VALIDATING, AUTHORIZED, TEST, ACTIVE, USED, CLOSED, LOCKED.
INSTRUMENT_VERSION_STATUSES = (
    "DRAFT",
    "VALIDATING",
    "AUTHORIZED",
    "TEST",
    "ACTIVE",
    "USED",
    "CLOSED",
    "LOCKED",
)


class Instrument(Base, PublicIdMixin, TimestampMixin):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    organization_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("organizations.id"), index=True
    )
    code: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    instrument_type: Mapped[str | None] = mapped_column(String(80))
    discipline: Mapped[str] = mapped_column(
        String(80), nullable=False, default="PSICOSOCIAL"
    )
    description: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    source_name: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    reproduction_terms: Mapped[str | None] = mapped_column(Text)
    method_code: Mapped[str | None] = mapped_column(String(50))
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONVariant, nullable=False, default=dict
    )

    versions: Mapped[list["InstrumentVersion"]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )
    project = relationship("Project", back_populates="instruments")


class InstrumentVersion(Base, PublicIdMixin, TimestampMixin):
    __tablename__ = "instrument_versions"
    __table_args__ = (UniqueConstraint("instrument_id", "version_code"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    version_code: Mapped[str] = mapped_column(String(80), nullable=False)
    version_name: Mapped[str | None] = mapped_column(String(255))
    edition: Mapped[str | None] = mapped_column(String(120))
    valid_from: Mapped[dt.date | None] = mapped_column(Date)
    valid_to: Mapped[dt.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    scoring_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="NOT_CONFIGURED"
    )
    instrument_kind: Mapped[str | None] = mapped_column(String(20))
    total_questions: Mapped[int | None] = mapped_column()
    psychosocial_questions: Mapped[int | None] = mapped_column()
    dimension_count: Mapped[int | None] = mapped_column()
    subdimension_count: Mapped[int] = mapped_column(nullable=False, default=0)
    source_reference: Mapped[str | None] = mapped_column(Text)
    reproduction_restrictions: Mapped[str | None] = mapped_column(Text)
    validation_notes: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    methodological_rules: Mapped[dict] = mapped_column(
        JSONVariant, nullable=False, default=dict
    )

    instrument: Mapped[Instrument] = relationship(back_populates="versions")
    questions: Mapped[list["Question"]] = relationship(  # noqa: F821
        back_populates="instrument_version", cascade="all, delete-orphan"
    )
    constructs: Mapped[list["Construct"]] = relationship(  # noqa: F821
        back_populates="instrument_version", cascade="all, delete-orphan"
    )
    option_sets: Mapped[list["OptionSet"]] = relationship(  # noqa: F821
        back_populates="instrument_version", cascade="all, delete-orphan"
    )
