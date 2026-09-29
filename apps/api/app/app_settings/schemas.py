from __future__ import annotations

import datetime as dt

from pydantic import Field

from app.constants import HARD_MAX_DAILY_CAP
from app.lib.schemas import CamelModel


class AppSettingsDTO(CamelModel):
    sender_name: str
    sender_title: str
    company_legal: str
    from_email: str
    reply_hint: str
    daily_cap: int
    effective_daily_cap: int
    hard_max_daily_cap: int
    recommended_daily_cap: int
    last_inbox_sync_at: dt.datetime | None
    updated_at: dt.datetime


class AppSettingsPatchRequest(CamelModel):
    sender_name: str | None = Field(default=None, max_length=120)
    sender_title: str | None = Field(default=None, max_length=120)
    company_legal: str | None = Field(default=None, max_length=200)
    reply_hint: str | None = None
    daily_cap: int | None = Field(default=None, ge=1, le=HARD_MAX_DAILY_CAP)
    # from_email is intentionally absent. Gmail forces the authenticated account
    # as the sender, so a hand-typed value could only ever disagree with reality;
    # it is written from the Gmail profile after OAuth.
