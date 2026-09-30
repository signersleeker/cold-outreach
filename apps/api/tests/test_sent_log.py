"""The dashboard's sent-emails month grid and per-day log.

This view answers "what did I actually send, and to whom". The properties that
matter: it is keyed on `sent_at`, so work that never left the mailbox is absent;
days are bucketed on the Brisbane boundary rather than UTC; and the names shown
next to each email survive the template or company being deleted afterwards.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.dashboard import service as dashboard_service
from app.sends.constants import (
    SEND_STATUS_BOUNCED,
    SEND_STATUS_FAILED,
    SEND_STATUS_QUEUED,
    SEND_STATUS_REPLIED_STOP,
    SEND_STATUS_SENT,
)
from app.sends.models.send_event import SendEvent

# FIXED_NOW is 2026-03-02T00:00Z == 2026-03-02 10:00 Brisbane.


def _event(
    db: Session,
    contact_id: uuid.UUID,
    sent_at: dt.datetime | None,
    status: str = SEND_STATUS_SENT,
    *,
    template_id: uuid.UUID | None = None,
    subject: str = "s",
    body: str = "b",
) -> SendEvent:
    row = SendEvent(
        contact_id=contact_id,
        template_id=template_id,
        subject_rendered=subject,
        body_rendered=body,
        rfc822_message_id=f"<{uuid.uuid4()}@test>",
        status=status,
        sent_at=sent_at,
    )
    db.add(row)
    db.commit()
    return row


# ------------------------------------------------------------------ calendar ----
def test_calendar_covers_the_whole_month_including_zeroes(db: Session, clock, app_settings) -> None:
    cal = dashboard_service.build_sent_calendar(db, clock=clock, year=2026, month=3)

    assert len(cal.days) == 31, "March has 31 days and every one must be present"
    assert [d.date for d in cal.days] == sorted(d.date for d in cal.days)
    assert cal.days[0].date == dt.date(2026, 3, 1)
    assert cal.days[-1].date == dt.date(2026, 3, 31)
    assert cal.month_total == 0
    assert cal.busiest_day == 0
    assert cal.today == dt.date(2026, 3, 2)
    assert cal.daily_cap == app_settings.daily_cap


def test_calendar_handles_february_and_the_december_rollover(db: Session, clock) -> None:
    assert len(dashboard_service.build_sent_calendar(db, clock=clock, year=2026, month=2).days) == 28
    leap = dashboard_service.build_sent_calendar(db, clock=clock, year=2028, month=2)
    assert len(leap.days) == 29
    december = dashboard_service.build_sent_calendar(db, clock=clock, year=2026, month=12)
    assert december.days[-1].date == dt.date(2026, 12, 31)


def test_calendar_counts_outcomes_as_subsets_of_sent(db: Session, clock, contact) -> None:
    day = dt.datetime(2026, 3, 10, 2, 0, tzinfo=dt.UTC)  # 12:00 Brisbane
    _event(db, contact.id, day, SEND_STATUS_SENT)
    _event(db, contact.id, day, SEND_STATUS_BOUNCED)
    _event(db, contact.id, day, SEND_STATUS_REPLIED_STOP)

    cal = dashboard_service.build_sent_calendar(db, clock=clock, year=2026, month=3)
    tenth = next(d for d in cal.days if d.date == dt.date(2026, 3, 10))

    assert tenth.sent == 3, "bounced and stopped still left the mailbox"
    assert tenth.bounced == 1
    assert tenth.stopped == 1
    assert cal.month_total == 3
    assert cal.busiest_day == 3


def test_calendar_excludes_work_that_never_left_the_mailbox(db: Session, clock, contact) -> None:
    _event(db, contact.id, None, SEND_STATUS_QUEUED)
    _event(db, contact.id, None, SEND_STATUS_FAILED)

    cal = dashboard_service.build_sent_calendar(db, clock=clock, year=2026, month=3)

    assert cal.month_total == 0, "queued and failed have no sent_at and are not history"


def test_calendar_buckets_on_the_brisbane_boundary(db: Session, clock, contact) -> None:
    """13:59Z and 14:01Z are the same UTC day but different Brisbane days."""
    _event(db, contact.id, dt.datetime(2026, 3, 10, 13, 59, tzinfo=dt.UTC))  # 10 Mar 23:59
    _event(db, contact.id, dt.datetime(2026, 3, 10, 14, 1, tzinfo=dt.UTC))  # 11 Mar 00:01

    by_date = {d.date: d.sent for d in dashboard_service.build_sent_calendar(
        db, clock=clock, year=2026, month=3
    ).days}

    assert by_date[dt.date(2026, 3, 10)] == 1
    assert by_date[dt.date(2026, 3, 11)] == 1


def test_calendar_claims_a_send_sitting_in_a_neighbouring_utc_month(
    db: Session, clock, contact
) -> None:
    """31 Mar 14:01Z is 1 Apr in Brisbane — it belongs to April's grid, not March's."""
    _event(db, contact.id, dt.datetime(2026, 3, 31, 14, 1, tzinfo=dt.UTC))

    march = dashboard_service.build_sent_calendar(db, clock=clock, year=2026, month=3)
    april = dashboard_service.build_sent_calendar(db, clock=clock, year=2026, month=4)

    assert march.month_total == 0
    assert april.month_total == 1
    assert next(d for d in april.days if d.date == dt.date(2026, 4, 1)).sent == 1


# ----------------------------------------------------------------- day list ----
def test_day_list_returns_the_rendered_snapshot_newest_first(db: Session, contact) -> None:
    _event(
        db,
        contact.id,
        dt.datetime(2026, 3, 10, 1, 0, tzinfo=dt.UTC),
        subject="first",
        body="body one",
    )
    _event(
        db,
        contact.id,
        dt.datetime(2026, 3, 10, 5, 0, tzinfo=dt.UTC),
        subject="second",
        body="body two",
    )

    emails = dashboard_service.list_sent_on(db, day=dt.date(2026, 3, 10))

    assert [e.subject for e in emails] == ["second", "first"]
    assert emails[0].body == "body two", "the exact bytes that went out, not the template"
    assert emails[0].contact_email == contact.email
    assert emails[0].contact_name == "Avery Stone"
    assert emails[0].company == "Northwind Mutual"


def test_day_list_spans_the_full_local_day_and_no_further(db: Session, contact) -> None:
    _event(db, contact.id, dt.datetime(2026, 3, 9, 14, 0, tzinfo=dt.UTC))  # 10 Mar 00:00 local
    _event(db, contact.id, dt.datetime(2026, 3, 10, 13, 59, tzinfo=dt.UTC))  # 10 Mar 23:59 local
    _event(db, contact.id, dt.datetime(2026, 3, 10, 14, 0, tzinfo=dt.UTC))  # 11 Mar 00:00 local

    emails = dashboard_service.list_sent_on(db, day=dt.date(2026, 3, 10))

    assert len(emails) == 2, "both local-day edges in, the next day's midnight out"


def test_day_list_excludes_queued_and_failed(db: Session, contact) -> None:
    _event(db, contact.id, dt.datetime(2026, 3, 10, 2, 0, tzinfo=dt.UTC))
    _event(db, contact.id, None, SEND_STATUS_QUEUED)
    _event(db, contact.id, None, SEND_STATUS_FAILED)

    assert len(dashboard_service.list_sent_on(db, day=dt.date(2026, 3, 10))) == 1


def test_day_list_survives_a_deleted_template_and_a_contact_with_no_company(
    db: Session, make_contact, template
) -> None:
    solo = make_contact(email="solo@nowhere.example", company="", first_name="", last_name="")
    _event(
        db,
        solo.id,
        dt.datetime(2026, 3, 10, 2, 0, tzinfo=dt.UTC),
        template_id=template.id,
    )

    named = dashboard_service.list_sent_on(db, day=dt.date(2026, 3, 10))
    assert named[0].template_name == template.name
    assert named[0].company == "", "no company is empty, not an error"
    assert named[0].contact_name == "", "falls back to the email in the UI"

    db.delete(template)
    db.commit()

    orphaned = dashboard_service.list_sent_on(db, day=dt.date(2026, 3, 10))
    assert len(orphaned) == 1, "deleting a template must not destroy the record of what was sent"
    assert orphaned[0].template_name == ""
    assert orphaned[0].subject == "s", "the rendered snapshot is still there"


def test_day_list_carries_the_error_for_a_bounce(db: Session, contact) -> None:
    row = _event(
        db, contact.id, dt.datetime(2026, 3, 10, 2, 0, tzinfo=dt.UTC), SEND_STATUS_BOUNCED
    )
    row.error = "550 5.1.1 unknown recipient"
    db.commit()

    emails = dashboard_service.list_sent_on(db, day=dt.date(2026, 3, 10))

    assert emails[0].status == SEND_STATUS_BOUNCED
    assert emails[0].error == "550 5.1.1 unknown recipient"


# -------------------------------------------------------------------- routes ----
def test_sent_calendar_route_returns_camel_case(client, db: Session, contact) -> None:
    _event(db, contact.id, dt.datetime(2026, 3, 10, 2, 0, tzinfo=dt.UTC))

    response = client.get("/api/v1/dashboard/sent/calendar", params={"year": 2026, "month": 3})

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert len(body["days"]) == 31
    assert {"date", "sent", "bounced", "stopped"} == set(body["days"][0])
    assert body["monthTotal"] == 1
    assert {"today", "timezone", "dailyCap", "busiestDay"} <= set(body)


def test_sent_calendar_route_is_not_shadowed_by_the_sent_route(client) -> None:
    """/dashboard/sent/calendar must not be parsed as /dashboard/sent.

    FastAPI matches in declaration order; the day route requires a `date` query
    param, so a wrong order would 400 here instead of returning a grid.
    """
    response = client.get("/api/v1/dashboard/sent/calendar", params={"year": 2026, "month": 3})

    assert response.status_code == 200, response.text
    assert "days" in response.json()["data"]


def test_sent_route_returns_the_day_with_meta(client, db: Session, contact) -> None:
    _event(db, contact.id, dt.datetime(2026, 3, 10, 2, 0, tzinfo=dt.UTC), subject="hello")

    response = client.get("/api/v1/dashboard/sent", params={"date": "2026-03-10"})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["meta"] == {"total": 1, "date": "2026-03-10"}
    row = payload["data"][0]
    assert row["subject"] == "hello"
    assert {"contactEmail", "contactName", "templateName", "sentAt", "gmailMessageId"} <= set(row)


def test_sent_route_rejects_a_bad_month(client) -> None:
    response = client.get("/api/v1/dashboard/sent/calendar", params={"year": 2026, "month": 13})

    assert response.status_code == 400
    assert response.json()["errors"], "should carry a message, not an empty list"
