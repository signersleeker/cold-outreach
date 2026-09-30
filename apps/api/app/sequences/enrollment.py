"""A contact's plan through an ordered template group with delays."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.sequences.constants import ENROLLMENT_ACTIVE, STEP_PENDING


class FollowUpEnrollment(Base):
    __tablename__ = "follow_up_enrollments"
    __table_args__ = (
        Index(
            "uq_follow_up_enrollments_active_contact",
            "contact_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_follow_up_enrollments_group", "group_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("template_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=ENROLLMENT_ACTIVE
    )
    assigned_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cancelled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    steps: Mapped[list[FollowUpStep]] = relationship(
        back_populates="enrollment",
        cascade="all, delete-orphan",
        order_by="FollowUpStep.position",
    )
    group = relationship("TemplateGroup")
    contact = relationship("Contact")


class FollowUpStep(Base):
    __tablename__ = "follow_up_steps"
    __table_args__ = (
        UniqueConstraint("enrollment_id", "position", name="uq_follow_up_steps_position"),
        Index(
            "ix_follow_up_steps_due",
            "status",
            "due_on",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("follow_up_enrollments.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("template_group_items.id", ondelete="SET NULL"),
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=STEP_PENDING
    )
    due_on: Mapped[dt.date | None] = mapped_column(Date)
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    send_event_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("send_events.id", ondelete="SET NULL"),
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    enrollment = relationship("FollowUpEnrollment", back_populates="steps")
    template = relationship("Template")
