from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pomogator.domain.content import AccessLevel
from pomogator.infrastructure.db.base import Base, IdMixin, TimestampMixin


class UserModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(255))


class CountryModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "countries"
    notion_page_id: Mapped[str] = mapped_column(String(64), unique=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    flag: Mapped[str] = mapped_column(String(16), default="🌍")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    content_version: Mapped[int] = mapped_column(Integer, default=0)
    pages: Mapped[list["PageModel"]] = relationship(back_populates="country")


class PageModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("country_id", "notion_page_id"),
        Index("ix_pages_country_parent", "country_id", "parent_id"),
    )
    country_id: Mapped[UUID] = mapped_column(ForeignKey("countries.id", ondelete="CASCADE"))
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"))
    notion_page_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    access_level: Mapped[AccessLevel] = mapped_column(Enum(AccessLevel, name="access_level"))
    document: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    country: Mapped[CountryModel] = relationship(back_populates="pages")


class ImageModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "images"
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    byte_size: Mapped[int] = mapped_column(Integer)


class PageImageModel(Base):
    __tablename__ = "page_images"
    __table_args__ = (UniqueConstraint("page_id", "image_id"),)
    page_id: Mapped[UUID] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), primary_key=True
    )
    image_id: Mapped[UUID] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), primary_key=True
    )


class EntitlementModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "entitlements"
    __table_args__ = (UniqueConstraint("user_id", "country_id"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    country_id: Mapped[UUID] = mapped_column(ForeignKey("countries.id", ondelete="CASCADE"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PaymentModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    country_id: Mapped[UUID] = mapped_column(ForeignKey("countries.id"))
    status: Mapped[str] = mapped_column(String(32))


class SyncRunModel(IdMixin, Base):
    __tablename__ = "sync_runs"
    country_id: Mapped[UUID] = mapped_column(ForeignKey("countries.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
