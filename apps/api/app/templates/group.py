from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TemplateGroup(Base):
    """A named, ordered set of templates with a delay after each previous send."""

    __tablename__ = "template_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list[TemplateGroupItem]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="TemplateGroupItem.position",
    )


class TemplateGroupItem(Base):
    __tablename__ = "template_group_items"
    __table_args__ = (
        UniqueConstraint("group_id", "template_id", name="uq_template_group_template"),
        Index("ix_template_group_items_group_position", "group_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("template_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # Days after the previous email was actually sent. Position 0 is always 0.
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    group = relationship("TemplateGroup", back_populates="items")
    template = relationship("Template")
