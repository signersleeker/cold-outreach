"""A validation verdict keyed by email, independent of any contact.

Deleting a contact leaves this row. A later import copies it onto the new
contact and does not call the validator again. Revalidate overwrites it.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, DateTime, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database import Base
from app.validation.base import ValidationResult


class EmailValidation(Base):
    __tablename__ = "email_validations"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_email_validations_email_lower"),
        CheckConstraint(
            "status IN ('valid', 'invalid', 'risky', 'unknown')",
            name="ck_email_validations_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    validator: Mapped[str] = mapped_column(String(32), nullable=False, server_default="")
    provider_status: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    provider_sub_status: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=""
    )
    provider_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


def get(db: Session, email: str) -> EmailValidation | None:
    return db.scalar(select(EmailValidation).where(EmailValidation.email == email.lower()))


def by_emails(db: Session, emails: list[str]) -> dict[str, EmailValidation]:
    normalized = list({email.lower() for email in emails if email})
    if not normalized:
        return {}
    rows = db.scalars(select(EmailValidation).where(EmailValidation.email.in_(normalized)))
    return {row.email: row for row in rows}


def upsert(
    db: Session,
    email: str,
    outcome: ValidationResult,
    *,
    validator_name: str,
    now: dt.datetime,
) -> EmailValidation:
    """Write a finished check. Callers skip this when ``outcome.durable`` is false."""
    normalized = email.lower()
    row = get(db, normalized)
    if row is None:
        row = EmailValidation(email=normalized, created_at=now)
    row.status = outcome.status
    row.detail = outcome.detail
    row.validator = validator_name[:32]
    row.provider_status = outcome.provider_status[:64]
    row.provider_sub_status = outcome.provider_sub_status[:64]
    row.provider_payload = outcome.provider_payload
    row.validated_at = now
    row.updated_at = now
    db.add(row)
    return row
