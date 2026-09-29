from __future__ import annotations

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
from app.dashboard.schemas import DashboardDTO, LastSendDTO
from app.gmail.oauth_service import GmailOAuthService
from app.lib.clock import Clock, brisbane_date
from app.sends.constants import SEND_STATUS_BOUNCED
from app.sends.models.send_event import SendEvent
from app.sends.services import counters
from app.sends.services.send import SendService
from app.suppressions import service as suppressions_service


def _count_contacts(db: Session, *where) -> int:  # noqa: ANN002
    return db.scalar(select(func.count()).select_from(Contact).where(*where)) or 0


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
