"""Follow-up enrollments: a contact walking an ordered group one send at a time."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.app_settings import service as settings_service
from app.contacts.constants import VALIDATION_INVALID
from app.contacts.contact import Contact
from app.lib.clock import Clock, date_in_zone, local_date
from app.lib.errors import AppError
from app.sends.models.send_event import SendEvent
from app.sequences.constants import (
    ENROLLMENT_ACTIVE,
    ENROLLMENT_CANCELLED,
    ENROLLMENT_COMPLETED,
    STEP_CANCELLED,
    STEP_PENDING,
    STEP_SENT,
)
from app.sequences.enrollment import FollowUpEnrollment, FollowUpStep
from app.templates import groups as groups_service
from app.templates.group import TemplateGroup


def _send_day(db: Session, moment: dt.datetime) -> dt.date:
    return date_in_zone(moment, settings_service.effective_timezone(db))


def _today(db: Session, clock: Clock) -> dt.date:
    return local_date(clock, settings_service.effective_timezone(db))


def _load_enrollment(db: Session, enrollment_id: uuid.UUID) -> FollowUpEnrollment | None:
    return db.scalar(
        select(FollowUpEnrollment)
        .options(
            selectinload(FollowUpEnrollment.steps).joinedload(FollowUpStep.template),
            selectinload(FollowUpEnrollment.group),
            selectinload(FollowUpEnrollment.contact).joinedload(Contact.company_ref),
        )
        .where(FollowUpEnrollment.id == enrollment_id)
    )


def get_active_for_contact(db: Session, contact_id: uuid.UUID) -> FollowUpEnrollment | None:
    return db.scalar(
        select(FollowUpEnrollment)
        .options(
            selectinload(FollowUpEnrollment.steps).joinedload(FollowUpStep.template),
            selectinload(FollowUpEnrollment.group),
            selectinload(FollowUpEnrollment.contact).joinedload(Contact.company_ref),
        )
        .where(
            FollowUpEnrollment.contact_id == contact_id,
            FollowUpEnrollment.status == ENROLLMENT_ACTIVE,
        )
    )


def require_active_for_contact(db: Session, contact_id: uuid.UUID) -> FollowUpEnrollment:
    enrollment = get_active_for_contact(db, contact_id)
    if enrollment is None:
        raise AppError(404, "no active follow-up plan on this contact")
    return enrollment


def next_pending_step(enrollment: FollowUpEnrollment) -> FollowUpStep | None:
    for step in enrollment.steps:
        if step.status == STEP_PENDING:
            return step
    return None


def _cancel_enrollment(enrollment: FollowUpEnrollment, *, now: dt.datetime) -> None:
    enrollment.status = ENROLLMENT_CANCELLED
    enrollment.cancelled_at = now
    enrollment.updated_at = now
    for step in enrollment.steps:
        if step.status == STEP_PENDING:
            step.status = STEP_CANCELLED
            step.updated_at = now


def cancel_for_contact(
    db: Session, contact_id: uuid.UUID, *, clock: Clock, commit: bool = True
) -> FollowUpEnrollment | None:
    enrollment = get_active_for_contact(db, contact_id)
    if enrollment is None:
        if commit:
            raise AppError(404, "no active follow-up plan on this contact")
        return None
    _cancel_enrollment(enrollment, now=clock.now())
    db.add(enrollment)
    if commit:
        db.commit()
        return _load_enrollment(db, enrollment.id)
    return enrollment


def enroll(
    db: Session,
    *,
    contact_id: uuid.UUID,
    group_id: uuid.UUID,
    clock: Clock,
    commit: bool = True,
) -> FollowUpEnrollment:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise AppError(404, "contact not found")
    group = groups_service.require(db, group_id)
    if not group.items:
        raise AppError(400, "that group has no templates")

    now = clock.now()
    today = _today(db, clock)
    existing = get_active_for_contact(db, contact_id)
    if existing is not None:
        _cancel_enrollment(existing, now=now)
        db.add(existing)

    enrollment = FollowUpEnrollment(
        contact_id=contact_id,
        group_id=group.id,
        status=ENROLLMENT_ACTIVE,
        assigned_at=now,
    )
    db.add(enrollment)
    db.flush()

    for item in group.items:
        db.add(
            FollowUpStep(
                enrollment_id=enrollment.id,
                group_item_id=item.id,
                template_id=item.template_id,
                position=item.position,
                delay_days=item.delay_days,
                status=STEP_PENDING,
                due_on=today if item.position == 0 else None,
            )
        )

    db.flush()
    if not commit:
        loaded = _load_enrollment(db, enrollment.id)
        assert loaded is not None
        return loaded

    db.commit()
    loaded = _load_enrollment(db, enrollment.id)
    assert loaded is not None
    return loaded


def advance_after_send(
    db: Session,
    *,
    contact_id: uuid.UUID,
    template_id: uuid.UUID,
    send_event: SendEvent,
    clock: Clock,
) -> FollowUpEnrollment | None:
    """Mark the matching pending step sent and schedule the next one.

    Advances only when the successful send is the next pending step's template.
    The caller commits.
    """
    enrollment = get_active_for_contact(db, contact_id)
    if enrollment is None:
        return None

    step = next_pending_step(enrollment)
    if step is None or step.template_id != template_id:
        return enrollment

    now = clock.now()
    send_day = _send_day(db, send_event.sent_at or now)
    step.status = STEP_SENT
    step.sent_at = send_event.sent_at or now
    step.send_event_id = send_event.id
    step.updated_at = now

    remaining = [s for s in enrollment.steps if s.status == STEP_PENDING]
    if not remaining:
        enrollment.status = ENROLLMENT_COMPLETED
        enrollment.completed_at = now
        enrollment.updated_at = now
        db.add(enrollment)
        return enrollment

    nxt = remaining[0]
    nxt.due_on = send_day + dt.timedelta(days=nxt.delay_days)
    nxt.updated_at = now
    enrollment.updated_at = now
    db.add_all([enrollment, step, nxt])
    return enrollment


def _retime_pending(
    enrollment: FollowUpEnrollment,
    *,
    today: dt.date,
    now: dt.datetime,
    tz,
) -> None:
    """Set due_on on the single next pending step; clear it on later pending steps."""
    last_sent: FollowUpStep | None = None
    for step in sorted(enrollment.steps, key=lambda s: s.position):
        if step.status == STEP_SENT:
            last_sent = step

    pending = [
        s
        for s in sorted(enrollment.steps, key=lambda s: s.position)
        if s.status == STEP_PENDING
    ]
    for index, step in enumerate(pending):
        if index > 0:
            step.due_on = None
            step.updated_at = now
            continue
        if last_sent is None:
            step.due_on = today
        else:
            sent_day = date_in_zone(last_sent.sent_at or now, tz)
            due = sent_day + dt.timedelta(days=step.delay_days)
            step.due_on = due if due >= today else today
        step.updated_at = now


def reconcile_group(db: Session, group: TemplateGroup, *, clock: Clock) -> None:
    """Sync enrollments with the group's current items. Caller commits.

    Active enrollments are always updated. A completed enrollment is reopened
    when the group gained steps that have not been sent yet.
    """
    tz = settings_service.effective_timezone(db)
    today = local_date(clock, tz)
    now = clock.now()
    enrollments = list(
        db.scalars(
            select(FollowUpEnrollment)
            .options(selectinload(FollowUpEnrollment.steps))
            .where(
                FollowUpEnrollment.group_id == group.id,
                FollowUpEnrollment.status.in_((ENROLLMENT_ACTIVE, ENROLLMENT_COMPLETED)),
            )
        )
    )

    for enrollment in enrollments:
        if enrollment.status == ENROLLMENT_COMPLETED:
            other = get_active_for_contact(db, enrollment.contact_id)
            if other is not None and other.id != enrollment.id:
                continue

        by_item = {
            step.group_item_id: step
            for step in enrollment.steps
            if step.group_item_id is not None
        }
        keep: set[uuid.UUID] = set()

        for item in group.items:
            existing = by_item.get(item.id)
            if existing is not None and existing.status == STEP_SENT:
                keep.add(existing.id)
                continue

            if existing is not None and existing.status == STEP_PENDING:
                existing.template_id = item.template_id
                existing.position = item.position
                existing.delay_days = item.delay_days
                existing.updated_at = now
                keep.add(existing.id)
                continue

            step = FollowUpStep(
                enrollment_id=enrollment.id,
                group_item_id=item.id,
                template_id=item.template_id,
                position=item.position,
                delay_days=item.delay_days,
                status=STEP_PENDING,
            )
            db.add(step)
            enrollment.steps.append(step)
            db.flush()
            keep.add(step.id)

        for step in list(enrollment.steps):
            if step.id in keep:
                continue
            if step.status == STEP_PENDING:
                enrollment.steps.remove(step)
                db.delete(step)

        _retime_pending(enrollment, today=today, now=now, tz=tz)
        if any(s.status == STEP_PENDING for s in enrollment.steps):
            enrollment.status = ENROLLMENT_ACTIVE
            enrollment.completed_at = None
        elif enrollment.steps and all(
            s.status == STEP_SENT for s in enrollment.steps if s.status != STEP_CANCELLED
        ):
            enrollment.status = ENROLLMENT_COMPLETED
            enrollment.completed_at = enrollment.completed_at or now
        enrollment.updated_at = now
        db.add(enrollment)


def due_steps_for_calendar(db: Session) -> list[FollowUpStep]:
    """Next pending step per active enrollment, excluding suppressed/invalid contacts."""
    enrollments = list(
        db.scalars(
            select(FollowUpEnrollment)
            .options(
                selectinload(FollowUpEnrollment.steps).joinedload(FollowUpStep.template),
                selectinload(FollowUpEnrollment.group),
                selectinload(FollowUpEnrollment.contact).joinedload(Contact.company_ref),
            )
            .where(FollowUpEnrollment.status == ENROLLMENT_ACTIVE)
        )
    )
    steps: list[FollowUpStep] = []
    for enrollment in enrollments:
        contact = enrollment.contact
        if contact is None or contact.suppressed or contact.validation_status == VALIDATION_INVALID:
            continue
        step = next_pending_step(enrollment)
        if step is None or step.due_on is None:
            continue
        steps.append(step)
    steps.sort(key=lambda s: (s.due_on or dt.date.min, s.enrollment.assigned_at))
    return steps
