from __future__ import annotations

import datetime as dt
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from time import monotonic

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.constants import (
    IMPORT_VALIDATION_BUDGET_SECONDS,
    IMPORT_VALIDATION_WORKERS,
    MAX_CSV_ROWS,
)
from app.contacts.constants import (
    VALIDATION_INVALID,
    VALIDATION_PENDING,
    VALIDATION_RISKY,
    VALIDATION_VALID,
)
from app.contacts.contact import Contact
from app.contacts.csv_import import ParsedRow, parse_csv
from app.lib.clock import Clock
from app.lib.errors import AppError
from app.sends.models.send_event import SendEvent
from app.suppressions import service as suppressions_service
from app.suppressions.constants import REASON_MANUAL
from app.suppressions.suppression import Suppression
from app.validation.base import EmailValidator, ValidationResult

_UNSUB_TOKEN_BYTES = 32


def new_unsub_token() -> str:
    """256 bits of entropy, stored on the row.

    Not derived from the email via HMAC: unsubscribe links outlive secrets, and
    rotating SECRET_KEY must never break an opt-out link already sitting in
    someone's inbox.
    """
    return secrets.token_urlsafe(_UNSUB_TOKEN_BYTES)


def _assign_unsub_token(db: Session, contact: Contact) -> None:
    """Set a unique token, retrying on the (astronomically unlikely) collision."""
    for _ in range(3):
        token = new_unsub_token()
        if not db.scalar(select(Contact.id).where(Contact.unsub_token == token)):
            contact.unsub_token = token
            return
    raise AppError(500, "could not allocate an unsubscribe token")


@dataclass
class ImportSummary:
    created: int = 0
    skipped_dupes: int = 0
    invalid: int = 0
    risky: int = 0
    valid: int = 0
    pending: int = 0
    missing_email: int = 0
    suppressed_existing: int = 0
    truncated: bool = False
    validator: str = ""
    headers_recognised: dict[str, str] = field(default_factory=dict)


# ------------------------------------------------------------------ queries ----
def get(db: Session, contact_id: uuid.UUID) -> Contact | None:
    return db.get(Contact, contact_id)


def require(db: Session, contact_id: uuid.UUID) -> Contact:
    contact = get(db, contact_id)
    if contact is None:
        raise AppError(404, "contact not found")
    return contact


def by_email(db: Session, email: str) -> Contact | None:
    return db.scalar(select(Contact).where(Contact.email == email.lower()))


def by_unsub_token(db: Session, token: str) -> Contact | None:
    if not token:
        return None
    return db.scalar(select(Contact).where(Contact.unsub_token == token))


def _apply_filter(query, status: str):  # noqa: ANN001 - SQLAlchemy Select generics
    if status == "ready":
        return query.where(
            Contact.validation_status.in_([VALIDATION_VALID]),
            Contact.suppressed.is_(False),
            Contact.last_sent_at.is_(None),
        )
    if status == "risky":
        return query.where(Contact.validation_status == VALIDATION_RISKY)
    if status == "invalid":
        return query.where(Contact.validation_status == VALIDATION_INVALID)
    if status == "pending":
        return query.where(Contact.validation_status == VALIDATION_PENDING)
    if status == "sent":
        return query.where(Contact.last_sent_at.is_not(None))
    if status == "suppressed":
        return query.where(Contact.suppressed.is_(True))
    return query


def search(
    db: Session,
    *,
    q: str = "",
    status: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Contact], int]:
    query = select(Contact)
    count_query = select(func.count()).select_from(Contact)

    if q.strip():
        pattern = f"%{q.strip().lower()}%"
        condition = or_(
            func.lower(Contact.email).like(pattern),
            func.lower(Contact.first_name).like(pattern),
            func.lower(Contact.last_name).like(pattern),
            func.lower(Contact.company).like(pattern),
            func.lower(Contact.title).like(pattern),
        )
        query = query.where(condition)
        count_query = count_query.where(condition)

    query = _apply_filter(query, status)
    count_query = _apply_filter(count_query, status)

    total = db.scalar(count_query) or 0
    rows = list(
        db.scalars(query.order_by(Contact.created_at.desc()).limit(limit).offset(offset))
    )
    return rows, total


# ------------------------------------------------------------------ mutation ----
def update(db: Session, contact_id: uuid.UUID, changes: dict[str, str]) -> Contact:
    contact = require(db, contact_id)
    editable = ("first_name", "last_name", "company", "title", "hook", "notes", "source")
    for name in editable:
        if name in changes and changes[name] is not None:
            setattr(contact, name, changes[name])
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def send_event_count(db: Session, contact_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(SendEvent).where(SendEvent.contact_id == contact_id)
        )
        or 0
    )


def delete(db: Session, contact_id: uuid.UUID, *, force: bool = False) -> dict[str, object]:
    """Remove a contact.

    Deleting cascades to its send_events, which is the record of what was sent to
    this person and when — so a contact that has been emailed is refused unless
    the caller explicitly forces it.

    The suppression list is deliberately untouched. It is keyed on email in its
    own table, so deleting a contact who opted out does not resurrect them: a
    later re-import recreates the contact already suppressed. Nothing in this app
    may turn a delete into a way to undo an opt-out.
    """
    contact = require(db, contact_id)
    sends = send_event_count(db, contact_id)

    if sends and not force:
        raise AppError(
            409,
            f"{contact.email} has {sends} send(s) on record. Deleting also deletes that "
            "history. Suppress instead to stop emailing them while keeping the record, "
            "or confirm the deletion.",
        )

    email = contact.email
    still_suppressed = suppressions_service.is_suppressed(db, email) is not None
    db.delete(contact)
    db.commit()
    return {
        "deleted": True,
        "email": email,
        "sendEventsDeleted": sends,
        "stillSuppressed": still_suppressed,
    }


def apply_validation(
    db: Session, contact: Contact, outcome: ValidationResult, *, now: dt.datetime
) -> None:
    """Record a validation verdict, auto-suppressing invalid addresses."""
    contact.validation_status = outcome.status
    contact.validation_detail = outcome.detail
    contact.validated_at = now
    db.add(contact)
    if outcome.status == VALIDATION_INVALID:
        suppressions_service.suppress(
            db,
            contact.email,
            reason=REASON_MANUAL,
            source=f"auto: validation ({outcome.detail})"[:200],
            now=now,
        )


def revalidate(
    db: Session, contact_id: uuid.UUID, *, validator: EmailValidator, clock: Clock
) -> Contact:
    contact = require(db, contact_id)
    outcome = validator.validate(contact.email)
    apply_validation(db, contact, outcome, now=clock.now())
    # A shared inbox used to be stored as invalid and auto-suppressed. Once a
    # later check says the mailbox exists, that automatic suppression is a
    # mistake. An opt-out, bounce, or complaint is left in place.
    if outcome.status == VALIDATION_VALID:
        existing = suppressions_service.is_suppressed(db, contact.email)
        if existing is not None and existing.source.startswith("auto: validation"):
            suppressions_service.unsuppress(db, contact.email)
    db.commit()
    db.refresh(contact)
    return contact


def create(
    db: Session,
    *,
    email: str,
    validator: EmailValidator,
    clock: Clock,
    **fields: str,
) -> Contact:
    from app.contacts.normalize import normalize_email

    normalized = normalize_email(email)
    if not normalized:
        raise AppError(400, "an email address is required")
    if by_email(db, normalized) is not None:
        raise AppError(409, f"{normalized} is already in the list")

    contact = Contact(email=normalized, **{k: v or "" for k, v in fields.items()})
    _assign_unsub_token(db, contact)
    db.add(contact)
    db.flush()
    apply_validation(db, contact, validator.validate(normalized), now=clock.now())
    db.commit()
    db.refresh(contact)
    return contact


def import_csv(
    db: Session,
    content: bytes,
    *,
    validator: EmailValidator,
    clock: Clock,
) -> ImportSummary:
    """Import a CSV, validating every new address inline.

    Validation is network-bound, so it runs on a small thread pool under a
    wall-clock budget. Rows the budget does not reach stay `pending` and can be
    validated later from the contact page — far better than a request that times
    out after importing nothing.
    """
    parsed = parse_csv(content, max_rows=MAX_CSV_ROWS)
    summary = ImportSummary(
        missing_email=parsed.missing_email,
        truncated=parsed.truncated,
        validator=getattr(validator, "name", "unknown"),
        headers_recognised=parsed.headers_recognised,
    )

    existing = {
        email.lower()
        for email in db.scalars(
            select(Contact.email).where(Contact.email.in_([r.email for r in parsed.rows]))
        )
    }
    fresh: list[ParsedRow] = []
    for row in parsed.rows:
        if row.email in existing:
            summary.skipped_dupes += 1
        else:
            fresh.append(row)

    # Captured before insert: an address already on the suppression list keeps
    # that state even on a fresh import, and must not be confused with one this
    # import auto-suppressed for failing validation.
    already_suppressed = {
        email.lower()
        for email in db.scalars(
            select(Suppression.email).where(Suppression.email.in_([r.email for r in fresh]))
        )
    }

    now = clock.now()
    created: list[Contact] = []
    for row in fresh:
        contact = Contact(
            email=row.email,
            first_name=row.first_name,
            last_name=row.last_name,
            company=row.company,
            title=row.title,
            hook=row.hook,
            notes=row.notes,
            source=row.source,
        )
        _assign_unsub_token(db, contact)
        db.add(contact)
        created.append(contact)
    db.flush()
    summary.created = len(created)

    # Network calls only — no Session touches a worker thread.
    outcomes: dict[str, ValidationResult] = {}
    if created:
        deadline = monotonic() + IMPORT_VALIDATION_BUDGET_SECONDS
        emails = [c.email for c in created]
        with ThreadPoolExecutor(max_workers=IMPORT_VALIDATION_WORKERS) as pool:
            futures = {pool.submit(validator.validate, email): email for email in emails}
            for future, email in futures.items():
                remaining = deadline - monotonic()
                if remaining <= 0:
                    future.cancel()
                    continue
                try:
                    outcomes[email] = future.result(timeout=remaining)
                except Exception:  # noqa: BLE001 - a failed check must stay pending
                    continue

    for contact in created:
        outcome = outcomes.get(contact.email)
        if outcome is None:
            summary.pending += 1
            continue
        apply_validation(db, contact, outcome, now=now)
        if outcome.status == VALIDATION_INVALID:
            summary.invalid += 1
        elif outcome.status == VALIDATION_RISKY:
            summary.risky += 1
        elif outcome.status == VALIDATION_VALID:
            summary.valid += 1
        else:
            summary.pending += 1

    for contact in created:
        if contact.email in already_suppressed:
            summary.suppressed_existing += 1
            suppression = suppressions_service.is_suppressed(db, contact.email)
            contact.suppressed = True
            if suppression is not None:
                contact.suppressed_reason = suppression.reason
                contact.suppressed_at = suppression.created_at
            db.add(contact)

    db.commit()
    return summary
