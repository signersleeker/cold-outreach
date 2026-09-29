from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Suppression(Base):
    """The authoritative do-not-email list.

    Keyed on email, not contact_id, so an address can be suppressed before it is
    ever imported — which is exactly what "add manually" needs to do. The send
    gate reads this table; contacts.suppressed is only a cache of it.
    """

    __tablename__ = "suppressions"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_suppressions_email_lower"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
