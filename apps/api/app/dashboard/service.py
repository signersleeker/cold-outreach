from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.app_settings import service as settings_service
from app.contacts.constants import (
    VALIDATION_INVALID,
    VALIDATION_PENDING,
    VALIDATION_RISKY,
    VALIDATION_VALID,
)
from app.contacts.contact import Contact
from app.dashboard.schemas import ActivityDayDTO, ActivityDTO, DashboardDTO, LastSendDTO
from app.gmail.oauth_service import GmailOAuthService
from app.lib.clock import BRISBANE, Clock, brisbane_date, brisbane_day_bounds, ensure_aware
from app.sends.constants import (
    SEND_STATUS_BOUNCED,
    SEND_STATUS_REPLIED_STOP,
)
from app.sends.models.send_event import SendEvent
from app.sends.services import counters
from app.sends.services.send import SendService
from app.suppressions import service as suppressions_service


def _count_contacts(db: Session, *where) -> int:  # noqa: ANN002
    return db.scalar(select(func.count()).select_from(Contact).where(*where)) or 0


def build_activity(db: Session, *, clock: Clock, days: int = 30) -> ActivityDTO:
    """Daily send volume for the last `days` Brisbane calendar days.

    Bucketing happens in Python rather than SQL: the window is at most a few
    hundred rows (the cap is the point of this product), and it keeps the
    Brisbane day boundary defined in exactly one place — brisbane_day_bounds —
    instead of duplicating the timezone rule in a database expression.
    """
    today = brisbane_date(clock)
    first_day = today - dt.timedelta(days=days - 1)
    window_start, _ = brisbane_day_bounds(first_day)

    rows = db.execute(
        select(SendEvent.sent_at, SendEvent.status).where(
            SendEvent.sent_at.is_not(None), SendEvent.sent_at >= window_start
        )
    ).all()

    # Every day in the range is present, including the zeroes — a gap in a time
    # axis must read as "nothing sent", never as "no bar here".
    buckets: dict[dt.date, dict[str, int]] = {
        first_day + dt.timedelta(days=offset): {"sent": 0, "bounced": 0, "stopped": 0}
        for offset in range(days)
    }

    for sent_at, status in rows:
        day = ensure_aware(sent_at).astimezone(BRISBANE).date()
        bucket = buckets.get(day)
        if bucket is None:  # A send timestamped in the future; not ours to chart.
            continue
        bucket["sent"] += 1
        if status == SEND_STATUS_BOUNCED:
            bucket["bounced"] += 1
        elif status == SEND_STATUS_REPLIED_STOP:
            bucket["stopped"] += 1

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


def build(
    db: Session, *, clock: Clock, oauth: GmailOAuthService, sends: SendService
) -> DashboardDTO:
    day = brisbane_date(clock)
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
        brisbane_date=day,
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
