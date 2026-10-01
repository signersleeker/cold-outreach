from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        Index("uq_companies_name_lower", text("lower(name)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[str] = mapped_column(String(500), nullable=False, server_default="", default="")
    linkedin_url: Mapped[str] = mapped_column(
        String(500), nullable=False, server_default="", default=""
    )
    industry: Mapped[str] = mapped_column(String(80), nullable=False, server_default="", default="")
    size: Mapped[str] = mapped_column(String(16), nullable=False, server_default="", default="")
    location: Mapped[str] = mapped_column(String(200), nullable=False, server_default="", default="")

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    contacts = relationship("Contact", back_populates="company_ref")
