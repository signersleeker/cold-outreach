from __future__ import annotations

import datetime as dt

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
