from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.sends.constants import SEND_STATUS_QUEUED


class SendEvent(Base):
    __tablename__ = "send_events"
    __table_args__ = (
        Index("ix_send_events_contact_created", "contact_id", "created_at"),
        Index("ix_send_events_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    contact_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    # Deleting a template must not destroy the record of what was sent.
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("templates.id", ondelete="SET NULL")
    )

    # The exact bytes that went out, including the signature, opt-out and unsub line.
    subject_rendered: Mapped[str] = mapped_column(Text, nullable=False)
    body_rendered: Mapped[str] = mapped_column(Text, nullable=False)

    # We generate the RFC 822 Message-ID ourselves and persist it *before*
    # calling Gmail. Without it, "Gmail accepted the message but our commit
    # failed" is unknowable; with it, app/cli/reconcile_sends.py can resolve the
    # true outcome via a `rfc822msgid:` search.
    rfc822_message_id: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    gmail_message_id: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=SEND_STATUS_QUEUED
    )
    error: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
