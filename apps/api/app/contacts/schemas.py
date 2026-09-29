from __future__ import annotations

import datetime as dt
import uuid

from pydantic import Field

from app.lib.schemas import CamelModel


class ContactDTO(CamelModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    company: str
    title: str
    source: str
    notes: str
    hook: str
    validation_status: str
    validation_detail: str
    validated_at: dt.datetime | None
    suppressed: bool
    suppressed_reason: str
    suppressed_at: dt.datetime | None
    last_sent_at: dt.datetime | None
    created_at: dt.datetime


class ContactCreateRequest(CamelModel):
    email: str = Field(min_length=3, max_length=320)
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    title: str = ""
    hook: str = ""
    notes: str = ""
    source: str = ""


class ContactPatchRequest(CamelModel):
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    title: str | None = None
    hook: str | None = None
    notes: str | None = None
    source: str | None = None


class SuppressContactRequest(CamelModel):
    reason: str = "manual"
    note: str = ""


class ImportSummaryDTO(CamelModel):
    created: int
    skipped_dupes: int
    invalid: int
    risky: int
    valid: int
    pending: int
    missing_email: int
    suppressed_existing: int
    truncated: bool
    validator: str
    headers_recognised: dict[str, str]
