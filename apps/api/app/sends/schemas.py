from __future__ import annotations

import datetime as dt
import uuid

from app.lib.schemas import CamelModel


class GateFindingDTO(CamelModel):
    code: str
    message: str
    requires_ack: bool


class SendPreviewRequest(CamelModel):
    contact_id: uuid.UUID
    template_id: uuid.UUID
    # Only ever clears a warning that requires acknowledgement. It can never
    # clear a blocker — see app/sends/gates.py.
    acknowledge: list[str] = []


class SendPreviewDTO(CamelModel):
    subject: str
    body: str
    unsub_url: str
    from_email: str
    sends_today: int
    daily_cap: int
    sendable: bool
    blockers: list[GateFindingDTO]
    warnings: list[GateFindingDTO]
    ack_required: list[str]


class SendRequest(CamelModel):
    contact_id: uuid.UUID
    template_id: uuid.UUID
    acknowledge: list[str] = []


class SendEventDTO(CamelModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    template_id: uuid.UUID | None
    subject_rendered: str
    body_rendered: str
    gmail_message_id: str
    status: str
    error: str
    sent_at: dt.datetime | None
    created_at: dt.datetime
