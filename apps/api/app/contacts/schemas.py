from __future__ import annotations

import datetime as dt
import uuid

from pydantic import Field

from app.lib.schemas import CamelModel
from app.sends.schemas import GateFindingDTO


class ContactStatsDTO(CamelModel):
    """Counts behind the Contacts header. Field names mirror the status filters."""

    all: int
    ready: int
    risky: int
    invalid: int
    pending: int
    sent: int
    suppressed: int
    validation_valid: int
    validation_unverified: int


class ContactDTO(CamelModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    company: str
    company_id: uuid.UUID | None = None
    company_industry: str = ""
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
    group_id: uuid.UUID | None = None
    group_name: str = ""


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
    skipped_existing_company: int = 0
    invalid: int
    risky: int
    valid: int
    pending: int
    missing_email: int
    suppressed_existing: int
    truncated: bool
    validator: str
    headers_recognised: dict[str, str]


class ImportPreviewDTO(CamelModel):
    headers: list[str]
    suggestions: dict[str, str | None]


class AssignmentContactDTO(CamelModel):
    contact_id: uuid.UUID
    email: str
    name: str
    blockers: list[GateFindingDTO] = []
    warnings: list[GateFindingDTO] = []


class GroupAssignmentPreviewDTO(CamelModel):
    group_id: uuid.UUID
    group_name: str
    template_id: uuid.UUID
    template_name: str
    will_send: int
    sends_today: int
    daily_cap: int
    sendable: list[AssignmentContactDTO]
    blocked: list[AssignmentContactDTO]
    warnings: list[AssignmentContactDTO]


class GroupAssignmentResultDTO(CamelModel):
    sent: int
    unassigned: int
    skipped: list[AssignmentContactDTO]
    failed: list[AssignmentContactDTO]


class GroupAssignmentPreviewRequest(CamelModel):
    group_id: uuid.UUID
    contact_ids: list[uuid.UUID] | None = None
    all_matching: bool = False
    q: str = ""
    status: str = "all"
    industry: str = ""
    group: str = ""
    acknowledge: list[str] = []


class GroupAssignmentRequest(CamelModel):
    group_id: uuid.UUID | None = None
    contact_ids: list[uuid.UUID] | None = None
    all_matching: bool = False
    q: str = ""
    status: str = "all"
    industry: str = ""
    group: str = ""
    acknowledge: list[str] = []
