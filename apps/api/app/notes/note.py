"""A note belongs to one parent, chosen by notable_type + notable_id.

That pair is the polymorphic association: the same table holds notes for
contacts and companies. There is no foreign key, because a single column
cannot reference both tables. notable_type says which table notable_id is in.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.notes.constants import NOTABLE_COMPANY, NOTABLE_CONTACT


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (
        CheckConstraint(
            f"notable_type IN ('{NOTABLE_CONTACT}', '{NOTABLE_COMPANY}')",
            name="ck_notes_notable_type",
        ),
        Index("ix_notes_notable", "notable_type", "notable_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    notable_type: Mapped[str] = mapped_column(String(16), nullable=False)
    notable_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
