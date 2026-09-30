from __future__ import annotations

import datetime as dt
import uuid

from app.lib.schemas import CamelModel


class LastSendDTO(CamelModel):
    email: str
    subject: str
    sent_at: dt.datetime | None


class ActivityDayDTO(CamelModel):
    """One calendar day of send activity (in the operator timezone).

    `sent` counts everything that actually left the mailbox that day, whatever
    the eventual outcome, so it lines up with the daily cap. `bounced` and
    `stopped` are subsets of it, not separate columns.
    """

    date: dt.date
    sent: int
    bounced: int
    stopped: int


class ActivityDTO(CamelModel):
    days: list[ActivityDayDTO]
    daily_cap: int
    total_sent: int
    busiest_day: int


class SentCalendarDayDTO(CamelModel):
    """One day of the sent-emails month grid, in the operator timezone.

    Same subset rule as ActivityDayDTO: `sent` is everything that left the
    mailbox that day, and `bounced`/`stopped` are outcomes within it.
    """

    date: dt.date
    sent: int
    bounced: int
    stopped: int


class SentCalendarDTO(CamelModel):
    today: dt.date
    timezone: str
    daily_cap: int
    month_total: int
    busiest_day: int
    days: list[SentCalendarDayDTO]


class SentEmailDTO(CamelModel):
    """One email that actually went out, with the names needed to read it.

    `subject` and `body` are the rendered snapshots stored on the send event,
    not the template's current text — a template edited or deleted since does
    not rewrite history, which is why `template_name` can be empty.
    """

    id: uuid.UUID
    sent_at: dt.datetime
    status: str
    error: str
    subject: str
    body: str
    gmail_message_id: str
    contact_id: uuid.UUID
    contact_email: str
    contact_name: str
    company: str
    template_name: str


class DashboardDTO(CamelModel):
    sends_today: int
    daily_cap: int
    today: dt.date
    timezone: str
    gmail_connected: bool
    gmail_email: str
    identity_complete: bool
    last_send: LastSendDTO | None
    contacts_total: int
    contacts_ready: int
    contacts_risky: int
    contacts_invalid: int
    contacts_pending: int
    suppressions_total: int
    suppressions_by_reason: dict[str, int]
    bounced_count: int
    stuck_queued_count: int
    last_inbox_sync_at: dt.datetime | None
