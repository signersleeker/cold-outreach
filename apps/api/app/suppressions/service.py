"""Suppression reads and writes.

`suppressions` is authoritative; `contacts.suppressed*` is a cache of it kept in
the same transaction, used only for list filtering and badges. Anything that
decides whether a send may happen must call is_suppressed() here, because a
suppression can exist for an address with no contact row at all — which is
exactly what "add manually before importing" produces.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.contacts.contact import Contact
from app.suppressions.suppression import Suppression


def is_suppressed(db: Session, email: str) -> Suppression | None:
    return db.scalar(select(Suppression).where(Suppression.email == email.lower()))


def suppress(
    db: Session, email: str, *, reason: str, source: str = "", now: dt.datetime | None = None
) -> Suppression:
    """Add an address to the do-not-email list and sync the contact cache.

    Idempotent: re-suppressing keeps the original reason and timestamp, because
    the first opt-out is the one that matters.
    """
    normalized = email.lower()
    db.execute(
        pg_insert(Suppression)
        .values(email=normalized, reason=reason, source=source)
        .on_conflict_do_nothing(index_elements=[Suppression.email])
    )
    row = db.scalar(select(Suppression).where(Suppression.email == normalized))
    assert row is not None

    contact = db.scalar(select(Contact).where(Contact.email == normalized))
    if contact is not None:
        contact.suppressed = True
        contact.suppressed_reason = row.reason
        contact.suppressed_at = row.created_at or now
        db.add(contact)
    return row


def unsuppress(db: Session, email: str) -> bool:
    """Remove a suppression. Only ever operator-initiated, never automatic."""
    normalized = email.lower()
    row = db.scalar(select(Suppression).where(Suppression.email == normalized))
    if row is None:
        return False
    db.delete(row)
    contact = db.scalar(select(Contact).where(Contact.email == normalized))
    if contact is not None:
        contact.suppressed = False
        contact.suppressed_reason = ""
        contact.suppressed_at = None
        db.add(contact)
    return True


def list_suppressions(db: Session, *, limit: int = 200, offset: int = 0) -> list[Suppression]:
    return list(
        db.scalars(
            select(Suppression)
            .order_by(Suppression.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def count_all(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Suppression)) or 0


def counts_by_reason(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Suppression.reason, func.count()).group_by(Suppression.reason)
    ).all()
    return {reason: count for reason, count in rows}
