"""Contact list group filter, and bulk start-sequence preview and confirm."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.contacts import service as contacts_service
from app.contacts.assignments import apply, preview
from app.contacts.constants import UNASSIGNED_GROUP
from app.lib.errors import AppError
from app.sends.constants import (
    GATE_DAILY_CAP_REACHED,
    GATE_UNRENDERED_MERGE_TAGS,
    GATE_VALIDATION_RISKY,
)
from app.sequences import service as sequences
from app.sequences.constants import STEP_SENT
from app.templates import groups as groups_service
from app.templates.group import TemplateGroup


def _group(db: Session, template, follow_up_template, name: str = "Touch sequence"):
    return groups_service.create(
        db, name=name, items=[(template.id, 0), (follow_up_template.id, 5)]
    )


def test_group_filter_scopes_the_list_and_the_stats(
    db: Session, make_contact, template, follow_up_template, clock
) -> None:
    group = _group(db, template, follow_up_template)
    assigned = make_contact(email="assigned@northwind.example")
    open_contact = make_contact(email="open@northwind.example")
    sequences.enroll(db, contact_id=assigned.id, group_id=group.id, clock=clock)

    rows, total = contacts_service.search(db, group=group.id)
    assert total == 1
    assert rows[0].id == assigned.id
    assert rows[0].group_id == group.id
    assert rows[0].group_name == "Touch sequence"

    unassigned, unassigned_total = contacts_service.search(db, group=UNASSIGNED_GROUP)
    assert unassigned_total == 1
    assert unassigned[0].id == open_contact.id
    assert unassigned[0].group_id is None
    assert unassigned[0].group_name == ""

    assert contacts_service.stats(db, group=group.id)["all"] == 1
    assert contacts_service.stats(db, group=UNASSIGNED_GROUP)["all"] == 1
    assert contacts_service.stats(db)["all"] == 2


def test_group_filter_route_rejects_an_unknown_group(client, make_contact) -> None:
    make_contact()
    missing = client.get("/api/v1/contacts", params={"group": str(uuid.uuid4())})
    assert missing.status_code == 400

    nonsense = client.get("/api/v1/contacts", params={"group": "not-a-group"})
    assert nonsense.status_code == 400


def test_list_route_returns_the_active_group(
    client, db: Session, make_contact, template, follow_up_template, clock
) -> None:
    group = _group(db, template, follow_up_template)
    contact = make_contact()
    sequences.enroll(db, contact_id=contact.id, group_id=group.id, clock=clock)

    response = client.get("/api/v1/contacts", params={"group": str(group.id)})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["groupId"] == str(group.id)
    assert body["data"][0]["groupName"] == "Touch sequence"

    stats = client.get("/api/v1/contacts/stats", params={"group": "none"})
    assert stats.status_code == 200, stats.text
    assert stats.json()["data"]["all"] == 0


def test_preview_blocks_a_missing_merge_field(
    db: Session,
    make_contact,
    template,
    follow_up_template,
    app_settings,
    connected_gmail,
    send_service,
) -> None:
    group = _group(db, template, follow_up_template)
    clean = make_contact(email="clean@northwind.example")
    blank = make_contact(email="blank@northwind.example", company="")

    result = preview(
        db,
        send_service,
        group_id=group.id,
        contact_ids=[clean.id, blank.id],
        all_matching=False,
        q="",
        status="all",
        industry="",
        group="",
        acknowledge=frozenset(),
    )

    assert result.will_send == 1
    assert [row.contact_id for row in result.sendable] == [clean.id]
    assert result.blocked[0].contact_id == blank.id
    assert GATE_UNRENDERED_MERGE_TAGS in {finding.code for finding in result.blocked[0].blockers}
    assert any("{{company}}" in finding.message for finding in result.blocked[0].blockers)


def test_preview_stops_at_the_daily_cap(
    db: Session,
    make_contact,
    template,
    follow_up_template,
    app_settings,
    connected_gmail,
    send_service,
) -> None:
    app_settings.daily_cap = 1
    db.add(app_settings)
    db.commit()
    group = _group(db, template, follow_up_template)
    first = make_contact(email="first@northwind.example")
    second = make_contact(email="second@northwind.example")

    result = preview(
        db,
        send_service,
        group_id=group.id,
        contact_ids=[first.id, second.id],
        all_matching=False,
        q="",
        status="all",
        industry="",
        group="",
        acknowledge=frozenset(),
    )

    assert result.will_send == 1
    assert result.sendable[0].contact_id == first.id
    assert result.blocked[0].contact_id == second.id
    assert GATE_DAILY_CAP_REACHED in {finding.code for finding in result.blocked[0].blockers}


def test_preview_holds_an_unacknowledged_warning(
    db: Session,
    make_contact,
    template,
    follow_up_template,
    app_settings,
    connected_gmail,
    send_service,
) -> None:
    group = _group(db, template, follow_up_template)
    risky = make_contact(email="risky@catchall.example", validation_status="risky")
    kwargs = {
        "group_id": group.id,
        "contact_ids": [risky.id],
        "all_matching": False,
        "q": "",
        "status": "all",
        "industry": "",
        "group": "",
    }

    held = preview(db, send_service, acknowledge=frozenset(), **kwargs)
    assert held.will_send == 0
    assert GATE_VALIDATION_RISKY in {finding.code for finding in held.blocked[0].warnings}

    released = preview(
        db, send_service, acknowledge=frozenset({GATE_VALIDATION_RISKY}), **kwargs
    )
    assert released.will_send == 1
    assert released.warnings[0].contact_id == risky.id


def test_preview_rejects_an_empty_group(db: Session, make_contact, send_service, app_settings) -> None:
    group = TemplateGroup(name="Empty")
    db.add(group)
    db.commit()
    contact = make_contact()

    with pytest.raises(AppError) as exc:
        preview(
            db,
            send_service,
            group_id=group.id,
            contact_ids=[contact.id],
            all_matching=False,
            q="",
            status="all",
            industry="",
            group="",
            acknowledge=frozenset(),
        )
    assert exc.value.status_code == 400


def test_confirm_sends_only_contacts_that_pass(
    db: Session,
    make_contact,
    template,
    follow_up_template,
    app_settings,
    connected_gmail,
    send_service,
    gmail,
    clock,
) -> None:
    group = _group(db, template, follow_up_template)
    clean = make_contact(email="clean@northwind.example")
    blank = make_contact(email="blank@northwind.example", company="")

    result = apply(
        db,
        send_service,
        clock=clock,
        group_id=group.id,
        contact_ids=[clean.id, blank.id],
        all_matching=False,
        q="",
        status="all",
        industry="",
        group="",
        acknowledge=frozenset(),
    )

    assert result.sent == 1
    assert [row.contact_id for row in result.skipped] == [blank.id]
    assert result.failed == []
    assert len(gmail.sent_raw) == 1

    enrolled = sequences.get_active_for_contact(db, clean.id)
    assert enrolled is not None
    assert enrolled.group_id == group.id
    assert enrolled.steps[0].status == STEP_SENT
    assert sequences.get_active_for_contact(db, blank.id) is None


def test_unassign_cancels_without_sending(
    db: Session,
    make_contact,
    template,
    follow_up_template,
    app_settings,
    send_service,
    gmail,
    clock,
) -> None:
    group = _group(db, template, follow_up_template)
    contact = make_contact()
    sequences.enroll(db, contact_id=contact.id, group_id=group.id, clock=clock)

    result = apply(
        db,
        send_service,
        clock=clock,
        group_id=None,
        contact_ids=[contact.id],
        all_matching=False,
        q="",
        status="all",
        industry="",
        group="",
        acknowledge=frozenset(),
    )

    assert result.sent == 0
    assert result.unassigned == 1
    assert sequences.get_active_for_contact(db, contact.id) is None
    assert gmail.sent_raw == []
