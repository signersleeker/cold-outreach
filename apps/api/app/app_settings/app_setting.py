from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

SETTINGS_ID = 1


class AppSetting(Base):
    """Singleton settings row. The CHECK constraint makes a second row impossible."""

    __tablename__ = "settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_settings_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SETTINGS_ID)

    sender_name: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    sender_title: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    company_legal: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")

    # Written from the Gmail profile after OAuth, never typed by hand. Gmail
    # forces the authenticated account as the sender, so an editable value here
    # could only ever disagree with reality.
    from_email: Mapped[str] = mapped_column(String(320), nullable=False, server_default="")

    # Operator-facing note shown in the send modal. Never an email header.
    reply_hint: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    daily_cap: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("20"))

    # When false, outbound mail skips the per-contact unsubscribe URL footer.
    include_unsub_link: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    last_inbox_sync_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
