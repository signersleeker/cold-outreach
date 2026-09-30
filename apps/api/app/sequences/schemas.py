from __future__ import annotations

import datetime as dt
import uuid

from app.lib.schemas import CamelModel


class FollowUpStepDTO(CamelModel):
    id: uuid.UUID
    group_item_id: uuid.UUID | None = None
    template_id: uuid.UUID
    template_name: str = ""
    subject: str = ""
    position: int
    delay_days: int
    status: str
    due_on: dt.date | None = None
    sent_at: dt.datetime | None = None


class FollowUpEnrollmentDTO(CamelModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    group_id: uuid.UUID
    group_name: str = ""
    status: str
    assigned_at: dt.datetime
    cancelled_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    steps: list[FollowUpStepDTO]
    next_step: FollowUpStepDTO | None = None


class FollowUpEnrollRequest(CamelModel):
    contact_id: uuid.UUID
    group_id: uuid.UUID


class CalendarDueItemDTO(CamelModel):
    enrollment_id: uuid.UUID
    step_id: uuid.UUID
    contact_id: uuid.UUID
    contact_email: str
    contact_name: str = ""
    company: str = ""
    group_id: uuid.UUID
    group_name: str = ""
    template_id: uuid.UUID
    template_name: str = ""
    position: int
    step_count: int
    due_on: dt.date
    overdue: bool = False
    past_cap: bool = False


class CalendarDayDTO(CamelModel):
    date: dt.date
    items: list[CalendarDueItemDTO]
    overdue_count: int = 0


class FollowUpCalendarDTO(CamelModel):
    today: dt.date
    timezone: str
    daily_cap: int
    sends_today: int
    remaining: int
    overdue_total: int
    days: list[CalendarDayDTO]
