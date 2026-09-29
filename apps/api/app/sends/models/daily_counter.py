from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, Integer, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyCounter(Base):
    """Successful-send slots consumed per Brisbane calendar day.

    `date` is the primary key so the reservation in
    app/sends/services/counters.py can use it as the ON CONFLICT target, making
    "increment unless at cap" a single atomic statement.
    """

    __tablename__ = "daily_counters"

    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
