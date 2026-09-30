"""Dashboard send-activity series and Contacts stats counts.

These two feed the charts, so the properties that matter are: every day in the
window is present (a gap must read as a zero bar, not a missing one), days are
bucketed on the Brisbane boundary rather than UTC, and every contact count comes
from the same filter the list uses.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.companies import service as companies_service
from app.contacts import service as contacts_service
from app.dashboard import service as dashboard_service
from app.sends.constants import (
    SEND_STATUS_BOUNCED,
    SEND_STATUS_QUEUED,
    SEND_STATUS_REPLIED_STOP,
    SEND_STATUS_SENT,
)
from app.sends.models.send_event import SendEvent


def _event(
    db: Session, contact_id: uuid.UUID, sent_at: dt.datetime | None, status: str
) -> SendEvent:
    row = SendEvent(
        contact_id=contact_id,
        subject_rendered="s",
        body_rendered="b",
        rfc822_message_id=f"<{uuid.uuid4()}@test>",
        status=status,
        sent_at=sent_at,
    )
    db.add(row)
    db.commit()
    return row


# ------------------------------------------------------------------ activity ----
def test_activity_returns_every_day_including_zeroes(db: Session, clock, app_settings) -> None:
    activity = dashboard_service.build_activity(db, clock=clock, days=30)

    assert len(activity.days) == 30
    assert activity.total_sent == 0
    assert all(day.sent == 0 for day in activity.days)
    # Contiguous and ascending, ending on the Brisbane "today".
    dates = [day.date for day in activity.days]
    assert dates == sorted(dates)
    assert dates[-1] - dates[0] == dt.timedelta(days=29)


def test_activity_counts_sends_and_subsets(db: Session, clock, contact, app_settings) -> None:
    today = clock.now()
    _event(db, contact.id, today, SEND_STATUS_SENT)
    _event(db, contact.id, today, SEND_STATUS_BOUNCED)
    _event(db, contact.id, today, SEND_STATUS_REPLIED_STOP)
    # Never left the mailbox, so it is not activity.
    _event(db, contact.id, None, SEND_STATUS_QUEUED)

    activity = dashboard_service.build_activity(db, clock=clock, days=30)
    last = activity.days[-1]

    assert last.sent == 3, "bounced and stopped still left the mailbox"
    assert last.bounced == 1
    assert last.stopped == 1
    assert activity.total_sent == 3
    assert activity.busiest_day == 3
    assert activity.daily_cap == app_settings.daily_cap


def test_activity_buckets_on_the_brisbane_boundary(
    db: Session, clock, contact, app_settings
) -> None:
    """13:59Z and 14:01Z are the same UTC day but different Brisbane days."""
    # FIXED_NOW is 2026-03-02T00:00Z == 2026-03-02 10:00 Brisbane.
    before_rollover = dt.datetime(2026, 3, 1, 13, 59, tzinfo=dt.UTC)  # 1 Mar 23:59 Brisbane
    after_rollover = dt.datetime(2026, 3, 1, 14, 1, tzinfo=dt.UTC)  # 2 Mar 00:01 Brisbane
    _event(db, contact.id, before_rollover, SEND_STATUS_SENT)
    _event(db, contact.id, after_rollover, SEND_STATUS_SENT)

    by_date = {d.date: d.sent for d in dashboard_service.build_activity(db, clock=clock).days}

    assert by_date[dt.date(2026, 3, 1)] == 1
    assert by_date[dt.date(2026, 3, 2)] == 1


def test_activity_excludes_sends_older_than_the_window(
    db: Session, clock, contact, app_settings
) -> None:
    _event(db, contact.id, clock.now() - dt.timedelta(days=40), SEND_STATUS_SENT)

    activity = dashboard_service.build_activity(db, clock=clock, days=30)

    assert activity.total_sent == 0


# --------------------------------------------------------------------- stats ----
def test_stats_counts_match_the_list_filters(db: Session, make_contact) -> None:
    """Every chip count must equal the row count you get by clicking it."""
    make_contact(email="ready@a.example", validation_status="valid")
    make_contact(email="risky@b.example", validation_status="risky")
    make_contact(email="invalid@c.example", validation_status="invalid")
    make_contact(email="pending@d.example", validation_status="pending")
    make_contact(
        email="sent@e.example", validation_status="valid", last_sent_at=dt.datetime.now(dt.UTC)
    )
    make_contact(email="supp@f.example", validation_status="valid", suppressed=True)

    stats = contacts_service.stats(db)

    for name in ("all", "ready", "risky", "invalid", "pending", "sent", "suppressed"):
        _, total = contacts_service.search(db, status=name, limit=1)
        assert stats[name] == total, f"{name} count disagrees with the list"

    assert stats["all"] == 6
    assert stats["ready"] == 1, "valid, never sent, not suppressed"
    assert stats["sent"] == 1
    assert stats["suppressed"] == 1


def test_industry_filter_scopes_the_list_and_the_stats(db: Session, make_contact) -> None:
    insurance = make_contact(email="a@ins.example", company="Northwind Mutual")
    make_contact(email="b@mine.example", company="Southgate Group")
    make_contact(email="c@blank.example", company="Blank Co")
    make_contact(email="d@solo.example", company="")

    assert insurance.company_id is not None
    companies_service.update(db, insurance.company_id, industry="insurance")
    mining = contacts_service.by_email(db, "b@mine.example")
    assert mining is not None and mining.company_id is not None
    companies_service.update(db, mining.company_id, industry="Mining & Metals")

    rows, total = contacts_service.search(db, industry="Insurance")
    assert total == 1
    assert [row.email for row in rows] == ["a@ins.example"]

    stats = contacts_service.stats(db, industry="Insurance")
    assert stats["all"] == 1
    assert stats["ready"] == 1
    _, listed = contacts_service.search(db, industry="Insurance", status="ready")
    assert listed == stats["ready"]

    unset, unset_total = contacts_service.search(db, industry="")
    assert unset_total == 2
    assert {row.email for row in unset} == {"c@blank.example", "d@solo.example"}
    assert contacts_service.stats(db, industry="")["all"] == 2
    assert contacts_service.stats(db)["all"] == 4


def test_industry_filter_route(client, db: Session, make_contact) -> None:
    contact = make_contact(email="a@ins.example", company="Northwind Mutual")
    make_contact(email="b@other.example", company="Other Co")

    assert contact.company_id is not None
    companies_service.update(
        db, contact.company_id, industry="Insurance", website="https://northwind.example"
    )

    response = client.get("/api/v1/contacts", params={"industry": "insurance"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["companyIndustry"] == "Insurance"
    assert body["data"][0]["companyWebsite"] == "https://northwind.example"

    stats = client.get("/api/v1/contacts/stats", params={"industry": "Insurance"})
    assert stats.status_code == 200, stats.text
    assert stats.json()["data"]["all"] == 1

    unset = client.get("/api/v1/contacts", params={"industry": "none"})
    assert unset.status_code == 200, unset.text
    assert unset.json()["meta"]["total"] == 1
    assert unset.json()["data"][0]["email"] == "b@other.example"

    unknown = client.get("/api/v1/contacts", params={"industry": "Space Mining"})
    assert unknown.status_code == 400


def test_stats_respects_search_and_company_scope(db: Session, make_contact) -> None:
    make_contact(email="avery@northwind.example", company="Northwind Mutual")
    other = make_contact(email="blake@southgate.example", company="Southgate Group")

    scoped = contacts_service.stats(db, q="southgate")
    assert scoped["all"] == 1

    by_company = contacts_service.stats(db, company_id=other.company_id)
    assert by_company["all"] == 1

    assert contacts_service.stats(db)["all"] == 2


def test_stats_route_is_not_shadowed_by_the_contact_id_route(client, make_contact) -> None:
    """/contacts/stats must not be parsed as /contacts/{contact_id}.

    FastAPI matches in declaration order, so moving the stats route below the
    dynamic one would turn "stats" into a malformed UUID and 422 here.
    """
    make_contact(email="avery@northwind.example")

    response = client.get("/api/v1/contacts/stats")

    assert response.status_code == 200, response.text
    assert response.json()["data"]["all"] == 1


def test_activity_route_returns_camel_case_series(client) -> None:
    response = client.get("/api/v1/dashboard/activity?days=7")

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert len(body["days"]) == 7
    assert {"date", "sent", "bounced", "stopped"} == set(body["days"][0])
    assert "dailyCap" in body and "totalSent" in body and "busiestDay" in body


def test_activity_route_rejects_an_out_of_range_window(client) -> None:
    """The app normalises validation failures to 400 in the error envelope."""
    response = client.get("/api/v1/dashboard/activity?days=400")

    assert response.status_code == 400
    assert response.json()["errors"], "should carry a message, not an empty list"


def test_stats_folds_unknown_into_unverified(db: Session, make_contact) -> None:
    make_contact(email="p@a.example", validation_status="pending")
    make_contact(email="u@b.example", validation_status="unknown")
    make_contact(email="v@c.example", validation_status="valid")

    stats = contacts_service.stats(db)

    assert stats["validation_unverified"] == 2, "pending and unknown are one bucket"
    assert stats["validation_valid"] == 1
    assert stats["pending"] == 1, "the pending *filter* stays strictly pending"
