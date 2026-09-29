from __future__ import annotations

import datetime as dt

from app.lib.schemas import CamelModel


class LastSendDTO(CamelModel):
    email: str
    subject: str
    sent_at: dt.datetime | None


class DashboardDTO(CamelModel):
    sends_today: int
    daily_cap: int
    brisbane_date: dt.date
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
