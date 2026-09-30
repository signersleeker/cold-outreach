from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Query, Response

from app.app_settings import service as settings_service
from app.deps import ClockDep, DbSession
from app.lib.clock import local_date
from app.lib.response import data_body
from app.sends.services import counters
from app.sequences import service
from app.sequences.enrollment import FollowUpEnrollment, FollowUpStep
from app.sequences.schemas import (
    CalendarDayDTO,
    CalendarDueItemDTO,
    FollowUpCalendarDTO,
    FollowUpEnrollmentDTO,
    FollowUpEnrollRequest,
    FollowUpStepDTO,
)

router = APIRouter(tags=["follow-ups"])


def _step_dto(step: FollowUpStep) -> FollowUpStepDTO:
    template = step.template
    return FollowUpStepDTO(
        id=step.id,
        group_item_id=step.group_item_id,
        template_id=step.template_id,
        template_name=template.name if template is not None else "",
        subject=template.subject if template is not None else "",
        position=step.position,
        delay_days=step.delay_days,
        status=step.status,
        due_on=step.due_on,
        sent_at=step.sent_at,
    )


def _enrollment_dto(enrollment: FollowUpEnrollment) -> FollowUpEnrollmentDTO:
    steps = [_step_dto(step) for step in enrollment.steps]
    nxt = service.next_pending_step(enrollment)
    group = enrollment.group
    return FollowUpEnrollmentDTO(
        id=enrollment.id,
        contact_id=enrollment.contact_id,
        group_id=enrollment.group_id,
        group_name=group.name if group is not None else "",
        status=enrollment.status,
        assigned_at=enrollment.assigned_at,
        cancelled_at=enrollment.cancelled_at,
        completed_at=enrollment.completed_at,
        steps=steps,
        next_step=_step_dto(nxt) if nxt is not None else None,
    )


def _contact_name(enrollment: FollowUpEnrollment) -> str:
    contact = enrollment.contact
    if contact is None:
        return ""
    return " ".join(p for p in (contact.first_name, contact.last_name) if p).strip()


def _item_dto(
    step: FollowUpStep,
    *,
    today: dt.date,
    past_cap: bool = False,
) -> CalendarDueItemDTO:
    enrollment = step.enrollment
    contact = enrollment.contact
    template = step.template
    group = enrollment.group
    return CalendarDueItemDTO(
        enrollment_id=enrollment.id,
        step_id=step.id,
        contact_id=enrollment.contact_id,
        contact_email=contact.email if contact is not None else "",
        contact_name=_contact_name(enrollment),
        company=contact.company if contact is not None else "",
        group_id=enrollment.group_id,
        group_name=group.name if group is not None else "",
        template_id=step.template_id,
        template_name=template.name if template is not None else "",
        position=step.position,
        step_count=len(enrollment.steps),
        due_on=step.due_on or today,
        overdue=bool(step.due_on and step.due_on < today),
        past_cap=past_cap,
    )


@router.get("/follow-ups/calendar")
def follow_up_calendar(
    db: DbSession,
    clock: ClockDep,
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
) -> Response:
    app_settings = settings_service.get_or_create(db)
    today = local_date(clock, settings_service.effective_timezone(db))
    cap = settings_service.effective_daily_cap(db)
    sent = counters.sends_today(db, today)
    remaining = max(0, cap - sent)

    steps = service.due_steps_for_calendar(db)
    overdue_total = sum(1 for s in steps if s.due_on is not None and s.due_on < today)

    first = dt.date(year, month, 1)
    if month == 12:
        last = dt.date(year + 1, 1, 1) - dt.timedelta(days=1)
    else:
        last = dt.date(year, month + 1, 1) - dt.timedelta(days=1)

    by_day: dict[dt.date, list[CalendarDueItemDTO]] = {}
    today_index = 0
    for step in steps:
        due = step.due_on
        if due is None:
            continue
        past_cap = False
        if due == today:
            past_cap = today_index >= remaining
            today_index += 1

        if due < first or due > last:
            # Overdue from a prior month is not on this grid; today carries overdue_count.
            continue

        by_day.setdefault(due, []).append(_item_dto(step, today=today, past_cap=past_cap))

    days: list[CalendarDayDTO] = []
    cursor = first
    while cursor <= last:
        items = by_day.get(cursor, [])
        overdue_on_day = overdue_total if cursor == today else 0
        days.append(
            CalendarDayDTO(date=cursor, items=items, overdue_count=overdue_on_day)
        )
        cursor += dt.timedelta(days=1)

    return data_body(
        FollowUpCalendarDTO(
            today=today,
            timezone=app_settings.timezone,
            daily_cap=cap,
            sends_today=sent,
            remaining=remaining,
            overdue_total=overdue_total,
            days=days,
        )
    )


@router.get("/contacts/{contact_id}/follow-up")
def get_contact_follow_up(contact_id: uuid.UUID, db: DbSession) -> Response:
    enrollment = service.get_active_for_contact(db, contact_id)
    if enrollment is None:
        return data_body(None)
    return data_body(_enrollment_dto(enrollment))


@router.post("/follow-ups")
def create_follow_up(
    payload: FollowUpEnrollRequest, db: DbSession, clock: ClockDep
) -> Response:
    enrollment = service.enroll(
        db, contact_id=payload.contact_id, group_id=payload.group_id, clock=clock
    )
    return data_body(_enrollment_dto(enrollment), status_code=201)


@router.delete("/contacts/{contact_id}/follow-up")
def cancel_contact_follow_up(
    contact_id: uuid.UUID, db: DbSession, clock: ClockDep
) -> Response:
    enrollment = service.cancel_for_contact(db, contact_id, clock=clock)
    return data_body(_enrollment_dto(enrollment) if enrollment else {"deleted": True})
