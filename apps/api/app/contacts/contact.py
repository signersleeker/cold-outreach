from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.contacts.constants import VALIDATION_PENDING
from app.database import Base


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_contacts_email_lower"),
        Index("ix_contacts_validation_status", "validation_status"),
        Index("ix_contacts_suppressed", "suppressed"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    last_name: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    company: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    title: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")

    # source and notes are the Spam Act evidence trail: where this address came
    # from and why contacting this person is defensible. Not decoration.
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    hook: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    validation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=VALIDATION_PENDING
    )
    validation_detail: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    validated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    # Denormalised cache of the suppressions table, for list filtering and
    # badges. `suppressions` is authoritative — the send gate reads that, never
    # this. See app/suppressions/service.py.
    suppressed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    suppressed_reason: Mapped[str] = mapped_column(String(16), nullable=False, server_default="")
    suppressed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    last_sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    # Random, stored (not derived from the email). Rotating SECRET_KEY must never
    # break unsubscribe links already sitting in someone's inbox.
    unsub_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
