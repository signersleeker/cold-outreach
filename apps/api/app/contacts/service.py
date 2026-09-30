from __future__ import annotations

import datetime as dt
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from time import monotonic

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.companies import service as companies_service
from app.companies.company import Company
from app.constants import (
    IMPORT_VALIDATION_BUDGET_SECONDS,
    IMPORT_VALIDATION_WORKERS,
    MAX_CSV_ROWS,
)
from app.contacts.constants import (
    UNASSIGNED_GROUP,
    VALIDATION_INVALID,
    VALIDATION_PENDING,
    VALIDATION_RISKY,
    VALIDATION_UNKNOWN,
    VALIDATION_VALID,
)
from app.contacts.contact import Contact
from app.contacts.csv_import import ParsedRow, parse_csv
from app.lib.clock import Clock
from app.lib.errors import AppError
from app.notes import service as notes_service
from app.notes.constants import NOTABLE_COMPANY, NOTABLE_CONTACT
from app.sends.models.send_event import SendEvent
from app.sequences.constants import ENROLLMENT_ACTIVE
from app.sequences.enrollment import FollowUpEnrollment
from app.suppressions import service as suppressions_service
from app.suppressions.constants import REASON_MANUAL
from app.suppressions.suppression import Suppression
from app.templates import groups as template_groups
from app.validation.base import EmailValidator, ValidationResult
from app.validation.email_validation import EmailValidation
from app.validation.email_validation import by_emails as validations_by_email
from app.validation.email_validation import get as validation_for_email
from app.validation.email_validation import upsert as upsert_validation

# A resolved list/stats scope: None is off, UNASSIGNED_GROUP is no active plan,
# and a UUID is that group's active plan.
GroupScope = uuid.UUID | str | None

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


def _assign_company(db: Session, contact: Contact, name: str | None) -> None:
    """Point the contact at a company by name, or clear the FK when blank."""
    if name is None:
        return
    company = companies_service.find_or_create(db, name)
    contact.company_id = company.id if company is not None else None
    contact.company_ref = company


@dataclass
class ImportSummary:
    created: int = 0
    skipped_dupes: int = 0
    skipped_existing_company: int = 0
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
def _contact_options():  # noqa: ANN202
    return (
        joinedload(Contact.company_ref),
        joinedload(Contact.active_enrollment).joinedload(FollowUpEnrollment.group),
    )


def get(db: Session, contact_id: uuid.UUID) -> Contact | None:
    return db.scalar(
        select(Contact).options(*_contact_options()).where(Contact.id == contact_id)
    )


def require(db: Session, contact_id: uuid.UUID) -> Contact:
    contact = get(db, contact_id)
    if contact is None:
        raise AppError(404, "contact not found")
    return contact


def by_email(db: Session, email: str) -> Contact | None:
    return db.scalar(
        select(Contact)
        .options(joinedload(Contact.company_ref))
        .where(Contact.email == email.lower())
    )


def by_unsub_token(db: Session, token: str) -> Contact | None:
    if not token:
        return None
    return db.scalar(
        select(Contact)
        .options(joinedload(Contact.company_ref))
        .where(Contact.unsub_token == token)
    )


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


def resolve_group_filter(db: Session, value: str) -> GroupScope:
    """Group scope for a contact list.

    None means the filter is off. UNASSIGNED_GROUP means no active plan. A
    UUID must be an existing template group.
    """
    stripped = value.strip()
    if not stripped:
        return None
    if stripped == UNASSIGNED_GROUP:
        return UNASSIGNED_GROUP
    try:
        group_id = uuid.UUID(stripped)
    except ValueError:
        raise AppError(400, "unknown group filter") from None
    if template_groups.get(db, group_id) is None:
        raise AppError(400, "unknown group filter")
    return group_id


def _active_contact_ids(group_id: uuid.UUID | None = None):  # noqa: ANN202
    stmt = select(FollowUpEnrollment.contact_id).where(
        FollowUpEnrollment.status == ENROLLMENT_ACTIVE
    )
    if group_id is not None:
        stmt = stmt.where(FollowUpEnrollment.group_id == group_id)
    return stmt


def _apply_scope(  # noqa: ANN001, ANN202
    query,
    *,
    q: str,
    company_id: uuid.UUID | None,
    industry: str | None = None,
    group: GroupScope = None,
):
    """Company, search, industry, and group narrowing that applies before the status filter.

    `industry` is None when that filter is off, '' for contacts with no industry
    (no company, or a company whose industry is blank), or a canonical name.

    `group` is None when that filter is off, UNASSIGNED_GROUP for contacts with
    no active plan, or a template group id.
    """
    if company_id is not None:
        query = query.where(Contact.company_id == company_id)

    if group == UNASSIGNED_GROUP:
        query = query.where(~Contact.id.in_(_active_contact_ids()))
    elif isinstance(group, uuid.UUID):
        query = query.where(Contact.id.in_(_active_contact_ids(group)))

    if industry is not None:
        if industry == "":
            query = query.where(
                or_(
                    Contact.company_id.is_(None),
                    Contact.company_id.in_(select(Company.id).where(Company.industry == "")),
                )
            )
        else:
            query = query.where(
                Contact.company_id.in_(select(Company.id).where(Company.industry == industry))
            )

    if q.strip():
        pattern = f"%{q.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Contact.email).like(pattern),
                func.lower(Contact.first_name).like(pattern),
                func.lower(Contact.last_name).like(pattern),
                func.lower(Contact.title).like(pattern),
                Contact.company_id.in_(
                    select(Company.id).where(func.lower(Company.name).like(pattern))
                ),
            )
        )
    return query


def stats(
    db: Session,
    *,
    q: str = "",
    company_id: uuid.UUID | None = None,
    industry: str | None = None,
    group: GroupScope = None,
) -> dict[str, int]:
    """Row counts per status filter, under the same scope the list is using.

    Every count goes through `_apply_filter`, the same function the list query
    uses, so a chip reading "Ready 42" cannot disagree with the 42 rows you get
    when you click it. `validation_*` are raw status tallies for the list
    composition bar, which is a different question from `ready` (that one also
    requires unsent and unsuppressed).
    """
    base = _apply_scope(
        select(func.count()).select_from(Contact),
        q=q,
        company_id=company_id,
        industry=industry,
        group=group,
    )

    counts = {
        name: db.scalar(_apply_filter(base, name)) or 0
        for name in ("all", "ready", "risky", "invalid", "pending", "sent", "suppressed")
    }
    counts["validation_valid"] = (
        db.scalar(base.where(Contact.validation_status == VALIDATION_VALID)) or 0
    )
    # pending and unknown both mean "no verdict", and the UI shows them as one
    # Unverified segment, so they are summed here rather than in the client.
    counts["validation_unverified"] = (
        db.scalar(
            base.where(
                Contact.validation_status.in_([VALIDATION_PENDING, VALIDATION_UNKNOWN])
            )
        )
        or 0
    )
    return counts


def matching_ids(
    db: Session,
    *,
    q: str = "",
    status: str = "all",
    company_id: uuid.UUID | None = None,
    industry: str | None = None,
    group: GroupScope = None,
) -> list[uuid.UUID]:
    """Every contact id under the list scope, in the same order as the list."""
    query = _apply_scope(
        select(Contact.id),
        q=q,
        company_id=company_id,
        industry=industry,
        group=group,
    )
    query = _apply_filter(query, status)
    return list(db.scalars(query.order_by(Contact.created_at.desc())))


def search(
    db: Session,
    *,
    q: str = "",
    status: str = "all",
    company_id: uuid.UUID | None = None,
    industry: str | None = None,
    group: GroupScope = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Contact], int]:
    query = _apply_scope(
        select(Contact).options(*_contact_options()),
        q=q,
        company_id=company_id,
        industry=industry,
        group=group,
    )
    count_query = _apply_scope(
        select(func.count()).select_from(Contact),
        q=q,
        company_id=company_id,
        industry=industry,
        group=group,
    )

    query = _apply_filter(query, status)
    count_query = _apply_filter(count_query, status)

    total = db.scalar(count_query) or 0
    rows = list(
        db.scalars(query.order_by(Contact.created_at.desc()).limit(limit).offset(offset)).unique()
    )
    return rows, total


# ------------------------------------------------------------------ mutation ----
def update(db: Session, contact_id: uuid.UUID, changes: dict[str, str]) -> Contact:
    contact = require(db, contact_id)
    editable = ("first_name", "last_name", "title", "hook", "notes", "source")
    for name in editable:
        if name in changes and changes[name] is not None:
            setattr(contact, name, changes[name])
    if "company" in changes and changes["company"] is not None:
        _assign_company(db, contact, changes["company"])
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return require(db, contact.id)


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

    email_validations is likewise left in place. A re-import copies that verdict
    onto the new contact instead of calling the validator again.
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
    notes_service.delete_for(db, NOTABLE_CONTACT, contact.id)
    db.delete(contact)
    db.commit()
    return {
        "deleted": True,
        "email": email,
        "sendEventsDeleted": sends,
        "stillSuppressed": still_suppressed,
    }


def _tally(summary: ImportSummary, status: str) -> None:
    if status == VALIDATION_INVALID:
        summary.invalid += 1
    elif status == VALIDATION_RISKY:
        summary.risky += 1
    elif status == VALIDATION_VALID:
        summary.valid += 1
    else:
        summary.pending += 1


def _suppress_if_invalid(db: Session, contact: Contact, *, detail: str, now: dt.datetime) -> None:
    if contact.validation_status != VALIDATION_INVALID:
        return
    suppressions_service.suppress(
        db,
        contact.email,
        reason=REASON_MANUAL,
        source=f"auto: validation ({detail})"[:200],
        now=now,
    )


def apply_stored(db: Session, contact: Contact, record: EmailValidation) -> None:
    """Copy a previous verdict onto a contact without calling the validator."""
    contact.validation_status = record.status
    contact.validation_detail = record.detail
    contact.validated_at = record.validated_at
    db.add(contact)
    _suppress_if_invalid(db, contact, detail=record.detail, now=record.validated_at)


def apply_validation(
    db: Session,
    contact: Contact,
    outcome: ValidationResult,
    *,
    now: dt.datetime,
    validator_name: str,
) -> None:
    """Record a validation verdict, auto-suppressing invalid addresses.

    A finished check is also stored by email. A transport failure updates this
    contact only, so the next import can try the checker again.
    """
    contact.validation_status = outcome.status
    contact.validation_detail = outcome.detail
    contact.validated_at = now
    db.add(contact)
    if outcome.durable:
        upsert_validation(
            db, contact.email, outcome, validator_name=validator_name, now=now
        )
    _suppress_if_invalid(db, contact, detail=outcome.detail, now=now)


def revalidate(
    db: Session, contact_id: uuid.UUID, *, validator: EmailValidator, clock: Clock
) -> Contact:
    contact = require(db, contact_id)
    outcome = validator.validate(contact.email)
    apply_validation(
        db,
        contact,
        outcome,
        now=clock.now(),
        validator_name=getattr(validator, "name", "unknown"),
    )
    # A shared inbox used to be stored as invalid and auto-suppressed. Once a
    # later check says the mailbox exists, that automatic suppression is a
    # mistake. An opt-out, bounce, or complaint is left in place.
    if outcome.status == VALIDATION_VALID:
        existing = suppressions_service.is_suppressed(db, contact.email)
        if existing is not None and existing.source.startswith("auto: validation"):
            suppressions_service.unsuppress(db, contact.email)
    db.commit()
    db.refresh(contact)
    return require(db, contact.id)


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

    company_name = fields.pop("company", "")
    contact = Contact(email=normalized, **{k: v or "" for k, v in fields.items()})
    _assign_company(db, contact, company_name)
    _assign_unsub_token(db, contact)
    db.add(contact)
    db.flush()
    stored = validation_for_email(db, normalized)
    if stored is not None:
        apply_stored(db, contact, stored)
    else:
        apply_validation(
            db,
            contact,
            validator.validate(normalized),
            now=clock.now(),
            validator_name=getattr(validator, "name", "unknown"),
        )
    db.commit()
    return require(db, contact.id)


def _attach_imported_notes(db: Session, contacts: list[Contact], rows: list[ParsedRow]) -> None:
    """Turn contact_notes and company_notes cells into note rows.

    The same company-note text on several rows of one company is stored once.
    A company note on a row with no company is skipped.
    """
    for contact, row in zip(contacts, rows, strict=True):
        notes_service.add(
            db,
            notable_type=NOTABLE_CONTACT,
            notable_id=contact.id,
            body=row.contact_notes,
        )
        if contact.company_id is not None:
            notes_service.add(
                db,
                notable_type=NOTABLE_COMPANY,
                notable_id=contact.company_id,
                body=row.company_notes,
                skip_duplicate=True,
            )


def import_csv(
    db: Session,
    content: bytes,
    *,
    validator: EmailValidator,
    clock: Clock,
    column_map: dict[str, str] | None = None,
    skip_validation: bool = False,
) -> ImportSummary:
    """Import a CSV, reusing a stored verdict and validating the rest inline.

    An address already in email_validations is copied onto the new contact and
    is not sent to the checker again, whether or not ``skip_validation`` is set.
    An invalid stored verdict still auto-suppresses.

    Validation of an address we have not seen is network-bound, so it runs on a
    small thread pool under a wall-clock budget. Rows the budget does not reach
    stay `pending` and can be validated later from the contact page.

    When ``skip_validation`` is set, an address with no stored verdict stays
    `pending` and nothing is written to email_validations. An address already
    on the suppression list stays suppressed either way.

    When ``column_map`` is provided it maps header text -> field name and is
    used instead of automatic alias matching.
    """
    parsed = parse_csv(content, max_rows=MAX_CSV_ROWS, column_map=column_map)
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
    # Company names already in the DB — rows naming these are skipped so a re-import
    # does not keep adding contacts under companies you already have.
    company_names = {r.company.strip().lower() for r in parsed.rows if r.company.strip()}
    existing_companies = {
        name.lower()
        for name in db.scalars(
            select(Company.name).where(
                func.lower(Company.name).in_(list(company_names))
            )
        )
    } if company_names else set()

    fresh: list[ParsedRow] = []
    for row in parsed.rows:
        if row.email in existing:
            summary.skipped_dupes += 1
            continue
        company_key = row.company.strip().lower()
        if company_key and company_key in existing_companies:
            summary.skipped_existing_company += 1
            continue
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
            title=row.title,
            hook=row.hook,
            notes=row.notes,
            source=row.source,
        )
        _assign_company(db, contact, row.company)
        if contact.company_ref is not None:
            companies_service.fill_blanks(
                contact.company_ref,
                website=row.website,
                industry=row.industry,
                location=row.location,
            )
        _assign_unsub_token(db, contact)
        db.add(contact)
        created.append(contact)
    db.flush()
    summary.created = len(created)
    _attach_imported_notes(db, created, fresh)

    stored = validations_by_email(db, [contact.email for contact in created])
    validator_name = getattr(validator, "name", "unknown")
    needs_check: list[Contact] = []
    for contact in created:
        record = stored.get(contact.email)
        if record is not None:
            apply_stored(db, contact, record)
            _tally(summary, record.status)
            continue
        if skip_validation:
            summary.pending += 1
            continue
        needs_check.append(contact)

    # Network calls only — no Session touches a worker thread.
    outcomes: dict[str, ValidationResult] = {}
    if needs_check:
        deadline = monotonic() + IMPORT_VALIDATION_BUDGET_SECONDS
        with ThreadPoolExecutor(max_workers=IMPORT_VALIDATION_WORKERS) as pool:
            futures = {
                pool.submit(validator.validate, contact.email): contact.email
                for contact in needs_check
            }
            for future, email in futures.items():
                remaining = deadline - monotonic()
                if remaining <= 0:
                    future.cancel()
                    continue
                try:
                    outcomes[email] = future.result(timeout=remaining)
                except Exception:  # noqa: BLE001 - a failed check must stay pending
                    continue

    for contact in needs_check:
        outcome = outcomes.get(contact.email)
        if outcome is None:
            summary.pending += 1
            continue
        apply_validation(
            db, contact, outcome, now=now, validator_name=validator_name
        )
        _tally(summary, outcome.status)

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
