"""Follow-up enrollments: delays, advance on send, and calendar."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.lib.clock import DEFAULT_TIMEZONE, local_date
from app.sequences import service as sequences
from app.sequences.constants import ENROLLMENT_ACTIVE, STEP_PENDING, STEP_SENT
from app.sends.models.send_event import SendEvent
from app.templates import groups as groups_service
from app.templates import service as templates_service
from tests.fakes import FrozenClock


def _sent_event(db: Session, *, contact_id, template_id, clock: FrozenClock, mid: str) -> SendEvent:
    event = SendEvent(
        contact_id=contact_id,
        template_id=template_id,
        subject_rendered="s",
        body_rendered="b",
        rfc822_message_id=mid,
        status="sent",
        sent_at=clock.now(),
    )
    db.add(event)
    db.flush()
    return event


def test_enroll_sets_first_step_due_today(db: Session, make_contact, template, follow_up_template, clock: FrozenClock):
    group = groups_service.create(
        db, name="Touch sequence", items=[(template.id, 0), (follow_up_template.id, 5)]
    )
    contact = make_contact()
    enrollment = sequences.enroll(
        db, contact_id=contact.id, group_id=group.id, clock=clock
    )
    assert enrollment.status == ENROLLMENT_ACTIVE
    assert len(enrollment.steps) == 2
    assert enrollment.steps[0].due_on == local_date(clock, DEFAULT_TIMEZONE)
    assert enrollment.steps[0].delay_days == 0
    assert enrollment.steps[1].due_on is None
    assert enrollment.steps[1].delay_days == 5


def test_advance_schedules_next_from_send_day(
    db: Session, make_contact, template, follow_up_template, clock: FrozenClock
):
    group = groups_service.create(
        db, name="Advance", items=[(template.id, 0), (follow_up_template.id, 5)]
    )
    contact = make_contact()
    sequences.enroll(db, contact_id=contact.id, group_id=group.id, clock=clock)
    event = _sent_event(
        db, contact_id=contact.id, template_id=template.id, clock=clock, mid="<x@test>"
    )
    sequences.advance_after_send(
        db,
        contact_id=contact.id,
        template_id=template.id,
        send_event=event,
        clock=clock,
    )
    db.commit()

    reloaded = sequences.get_active_for_contact(db, contact.id)
    assert reloaded is not None
    assert reloaded.steps[0].status == STEP_SENT
    assert reloaded.steps[1].status == STEP_PENDING
    assert reloaded.steps[1].due_on == local_date(clock, DEFAULT_TIMEZONE) + dt.timedelta(days=5)


def test_append_step_after_sequence_finished_schedules_from_last_send(
    db: Session, make_contact, template, follow_up_template, clock: FrozenClock
):
    group = groups_service.create(
        db, name="Appendable", items=[(template.id, 0), (follow_up_template.id, 5)]
    )
    contact = make_contact()
    sequences.enroll(db, contact_id=contact.id, group_id=group.id, clock=clock)

    event1 = _sent_event(
        db, contact_id=contact.id, template_id=template.id, clock=clock, mid="<a@test>"
    )
    sequences.advance_after_send(
        db, contact_id=contact.id, template_id=template.id, send_event=event1, clock=clock
    )
    db.commit()

    later = FrozenClock(clock.now() + dt.timedelta(days=10))
    event2 = _sent_event(
        db,
        contact_id=contact.id,
        template_id=follow_up_template.id,
        clock=later,
        mid="<b@test>",
    )
    sequences.advance_after_send(
        db,
        contact_id=contact.id,
        template_id=follow_up_template.id,
        send_event=event2,
        clock=later,
    )
    db.commit()

    # Another week after email 2 — the 5-day delay has already elapsed.
    much_later = FrozenClock(later.now() + dt.timedelta(days=7))
    third = templates_service.create(
        db, name="Email 4", subject="s", body="Hi {{first_name}}"
    )
    groups_service.update(
        db,
        group.id,
        items=[
            (template.id, 0),
            (follow_up_template.id, 5),
            (third.id, 5),
        ],
        clock=much_later,
    )

    enrollment = sequences.get_active_for_contact(db, contact.id)
    assert enrollment is not None
    assert enrollment.status == ENROLLMENT_ACTIVE
    assert len(enrollment.steps) == 3
    assert enrollment.steps[2].template_id == third.id
    assert enrollment.steps[2].status == STEP_PENDING
    assert enrollment.steps[2].due_on == local_date(much_later, DEFAULT_TIMEZONE)


def test_is_current_due_template(
    db: Session, make_contact, template, follow_up_template, clock: FrozenClock
):
    group = groups_service.create(
        db, name="Due check", items=[(template.id, 0), (follow_up_template.id, 5)]
    )
    contact = make_contact()
    sequences.enroll(db, contact_id=contact.id, group_id=group.id, clock=clock)
    today = local_date(clock, DEFAULT_TIMEZONE)
    assert sequences.is_current_due_template(
        db, contact_id=contact.id, template_id=template.id, today=today
    )
    assert not sequences.is_current_due_template(
        db, contact_id=contact.id, template_id=follow_up_template.id, today=today
    )


def test_calendar_lists_due_steps(
    db: Session, make_contact, template, follow_up_template, clock: FrozenClock
):
    group = groups_service.create(
        db, name="Calendar", items=[(template.id, 0), (follow_up_template.id, 5)]
    )
    contact = make_contact(email="due@example.com", first_name="Ada")
    sequences.enroll(db, contact_id=contact.id, group_id=group.id, clock=clock)
    steps = sequences.due_steps_for_calendar(db)
    assert len(steps) == 1
    assert steps[0].enrollment.contact_id == contact.id
    assert steps[0].due_on == local_date(clock, DEFAULT_TIMEZONE)
