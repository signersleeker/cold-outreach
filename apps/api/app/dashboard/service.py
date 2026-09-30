from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.app_settings import service as settings_service
from app.companies.company import Company
from app.contacts.constants import (
    VALIDATION_INVALID,
    VALIDATION_PENDING,
    VALIDATION_RISKY,
    VALIDATION_VALID,
)
from app.contacts.contact import Contact
from app.dashboard.schemas import (
    ActivityDayDTO,
    ActivityDTO,
    DashboardDTO,
    LastSendDTO,
    SentCalendarDayDTO,
    SentCalendarDTO,
    SentEmailDTO,
)
from app.gmail.oauth_service import GmailOAuthService
from app.lib.clock import Clock, date_in_zone, day_bounds, local_date
from app.sends.constants import (
    SEND_STATUS_BOUNCED,
    SEND_STATUS_REPLIED_STOP,
)
from app.sends.models.send_event import SendEvent
from app.sends.services import counters
from app.sends.services.send import SendService
from app.suppressions import service as suppressions_service
from app.templates.template import Template


def _count_contacts(db: Session, *where) -> int:  # noqa: ANN002
    return db.scalar(select(func.count()).select_from(Contact).where(*where)) or 0


def _empty_buckets(first_day: dt.date, days: int) -> dict[dt.date, dict[str, int]]:
    """Every day in the range, including the zeroes — a gap in a time axis must
    read as "nothing sent", never as "no bar here"."""
    return {
        first_day + dt.timedelta(days=offset): {"sent": 0, "bounced": 0, "stopped": 0}
        for offset in range(days)
    }


def _bucket_sends(  # noqa: ANN001
    rows, buckets: dict[dt.date, dict[str, int]], tz: ZoneInfo
) -> None:
    """Tally (sent_at, status) pairs into per-day buckets keyed on the operator zone.

    Bucketing happens in Python rather than SQL: the windows here are at most a
    few hundred rows (the cap is the point of this product), and it keeps the
    day boundary defined in exactly one place — day_bounds/date_in_zone —
    instead of duplicating the timezone rule in a database expression.
    """
    for sent_at, status in rows:
        bucket = buckets.get(date_in_zone(sent_at, tz))
        if bucket is None:  # Outside the requested window; not ours to count.
            continue
        bucket["sent"] += 1
        if status == SEND_STATUS_BOUNCED:
            bucket["bounced"] += 1
        elif status == SEND_STATUS_REPLIED_STOP:
            bucket["stopped"] += 1


def build_activity(db: Session, *, clock: Clock, days: int = 30) -> ActivityDTO:
    """Daily send volume for the last `days` calendar days in the operator zone."""
    tz = settings_service.effective_timezone(db)
    today = local_date(clock, tz)
    first_day = today - dt.timedelta(days=days - 1)
    window_start, _ = day_bounds(first_day, tz)

    rows = db.execute(
        select(SendEvent.sent_at, SendEvent.status).where(
            SendEvent.sent_at.is_not(None), SendEvent.sent_at >= window_start
        )
    ).all()

    buckets = _empty_buckets(first_day, days)
    _bucket_sends(rows, buckets, tz)

    series = [
        ActivityDayDTO(date=day, sent=c["sent"], bounced=c["bounced"], stopped=c["stopped"])
        for day, c in sorted(buckets.items())
    ]

    return ActivityDTO(
        days=series,
        daily_cap=settings_service.effective_daily_cap(db),
        total_sent=sum(d.sent for d in series),
        busiest_day=max((d.sent for d in series), default=0),
    )


def _month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    """First and last calendar date of a month, inclusive."""
    first = dt.date(year, month, 1)
    if month == 12:
        last = dt.date(year + 1, 1, 1) - dt.timedelta(days=1)
    else:
        last = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    return first, last


def build_sent_calendar(db: Session, *, clock: Clock, year: int, month: int) -> SentCalendarDTO:
    """Per-day counts of email that actually went out, for one month's grid.

    Keyed on `sent_at`, so queued and failed events — which never left the
    mailbox and carry no sent_at — are absent by construction. They are the
    stuck-queued callout's business, not this view's.
    """
    tz = settings_service.effective_timezone(db)
    first, last = _month_bounds(year, month)
    window_start, _ = day_bounds(first, tz)
    _, window_end = day_bounds(last, tz)

    rows = db.execute(
        select(SendEvent.sent_at, SendEvent.status).where(
            SendEvent.sent_at.is_not(None),
            SendEvent.sent_at >= window_start,
            SendEvent.sent_at < window_end,
        )
    ).all()

    buckets = _empty_buckets(first, (last - first).days + 1)
    _bucket_sends(rows, buckets, tz)

    days = [
        SentCalendarDayDTO(date=day, sent=c["sent"], bounced=c["bounced"], stopped=c["stopped"])
        for day, c in sorted(buckets.items())
    ]

    return SentCalendarDTO(
        today=local_date(clock, tz),
        # The zone actually used for bucketing, so the label can never disagree
        # with the grid — effective_timezone falls back when the setting is blank.
        timezone=tz.key,
        daily_cap=settings_service.effective_daily_cap(db),
        month_total=sum(d.sent for d in days),
        busiest_day=max((d.sent for d in days), default=0),
        days=days,
    )


def list_sent_on(db: Session, *, day: dt.date, limit: int = 200) -> list[SentEmailDTO]:
    """Every email sent on one calendar day in the operator zone, newest first.

    The rendered body rides along: a day holds at most the daily cap's worth of
    rows, so the payload stays small and the detail view needs no second fetch.
    """
    start, end = day_bounds(day, settings_service.effective_timezone(db))

    rows = db.execute(
        select(SendEvent, Contact, Company.name, Template.name)
        .join(Contact, Contact.id == SendEvent.contact_id)
        .outerjoin(Company, Company.id == Contact.company_id)
        .outerjoin(Template, Template.id == SendEvent.template_id)
        .where(SendEvent.sent_at >= start, SendEvent.sent_at < end)
        .order_by(SendEvent.sent_at.desc())
        .limit(limit)
    ).all()

    return [
        SentEmailDTO(
            id=event.id,
            sent_at=event.sent_at,
            status=event.status,
            error=event.error,
            subject=event.subject_rendered,
            body=event.body_rendered,
            gmail_message_id=event.gmail_message_id,
            contact_id=contact.id,
            contact_email=contact.email,
            contact_name=" ".join(p for p in (contact.first_name, contact.last_name) if p).strip(),
            company=company or "",
            template_name=template or "",
        )
        for event, contact, company, template in rows
    ]


def build(
    db: Session, *, clock: Clock, oauth: GmailOAuthService, sends: SendService
) -> DashboardDTO:
    tz = settings_service.effective_timezone(db)
    day = local_date(clock, tz)
    app_settings = settings_service.get_or_create(db)
    gmail_row = oauth.current(db)

    last_event = sends.last_sent(db)
    last_send = None
    if last_event is not None:
        contact = db.get(Contact, last_event.contact_id)
        last_send = LastSendDTO(
            email=contact.email if contact else "",
            subject=last_event.subject_rendered,
            sent_at=last_event.sent_at,
        )

    bounced = (
        db.scalar(
            select(func.count())
            .select_from(SendEvent)
            .where(SendEvent.status == SEND_STATUS_BOUNCED)
        )
        or 0
    )

    dto = DashboardDTO(
        sends_today=counters.sends_today(db, day),
        daily_cap=settings_service.effective_daily_cap(db),
        today=day,
        timezone=app_settings.timezone,
        gmail_connected=oauth.is_connected(db),
        gmail_email=gmail_row.email if gmail_row else "",
        identity_complete=settings_service.identity_complete(app_settings),
        last_send=last_send,
        contacts_total=_count_contacts(db),
        contacts_ready=_count_contacts(
            db,
            Contact.validation_status == VALIDATION_VALID,
            Contact.suppressed.is_(False),
            Contact.last_sent_at.is_(None),
        ),
        contacts_risky=_count_contacts(db, Contact.validation_status == VALIDATION_RISKY),
        contacts_invalid=_count_contacts(db, Contact.validation_status == VALIDATION_INVALID),
        contacts_pending=_count_contacts(db, Contact.validation_status == VALIDATION_PENDING),
        suppressions_total=suppressions_service.count_all(db),
        suppressions_by_reason=suppressions_service.counts_by_reason(db),
        bounced_count=bounced,
        stuck_queued_count=len(sends.stuck_queued(db)),
        last_inbox_sync_at=app_settings.last_inbox_sync_at,
    )
    db.commit()
    return dto
