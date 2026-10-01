"""Changing a contact's email.

The address is the identity on every send, so it can move only while nothing
has gone out. A permanent Gmail rejection does not count: the message never
left, and the typo is the thing the operator is there to fix.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.contacts import service as contacts_service
from app.lib.errors import AppError
from app.sends.constants import SEND_STATUS_FAILED, SEND_STATUS_SENT
from app.sends.models.send_event import SendEvent
from app.suppressions import service as suppressions_service
from app.suppressions.constants import REASON_MANUAL, REASON_UNSUB
from app.validation.base import ValidationResult
from app.validation.email_validation import get as validation_for_email
from app.validation.email_validation import upsert as upsert_validation


def add_send(db: Session, contact, clock, *, status: str = SEND_STATUS_SENT) -> SendEvent:
    event = SendEvent(
        contact_id=contact.id,
        template_id=None,
        subject_rendered="shadow AI",
        body_rendered="body",
        rfc822_message_id=f"<{uuid.uuid4()}@kinnatic.ai>",
        status=status,
        sent_at=clock.now() if status == SEND_STATUS_SENT else None,
    )
    db.add(event)
    db.commit()
    return event


def test_email_can_be_corrected_before_anything_is_sent(db: Session, contact) -> None:
    updated = contacts_service.update(
        db, contact.id, {"email": "  Avery.Fixed@Northwind.example "}
    )

    assert updated.email == "avery.fixed@northwind.example"
    assert updated.validation_status == "pending"
    assert updated.validation_detail == ""
    assert updated.validated_at is None
    assert contacts_service.by_email(db, "avery.stone@northwind.example") is None


def test_saving_the_same_address_leaves_validation_alone(db: Session, contact) -> None:
    updated = contacts_service.update(
        db, contact.id, {"email": "Avery.Stone@Northwind.example"}
    )

    assert updated.email == "avery.stone@northwind.example"
    assert updated.validation_status == "valid"


def test_a_failed_send_still_allows_the_correction(db: Session, contact, clock) -> None:
    add_send(db, contact, clock, status=SEND_STATUS_FAILED)

    updated = contacts_service.update(db, contact.id, {"email": "fixed@northwind.example"})

    assert updated.email == "fixed@northwind.example"


def test_a_sent_email_locks_the_address(db: Session, contact, clock) -> None:
    add_send(db, contact, clock)
    original = contact.email

    with pytest.raises(AppError) as exc:
        contacts_service.update(db, contact.id, {"email": "other@northwind.example"})

    assert exc.value.status_code == 409
    assert "can't be changed" in exc.value.messages[0]
    assert contacts_service.require(db, contact.id).email == original


def test_an_ambiguous_send_locks_the_address_via_last_sent_at(db: Session, contact, clock) -> None:
    contact.last_sent_at = clock.now()
    db.add(contact)
    db.commit()

    with pytest.raises(AppError) as exc:
        contacts_service.update(db, contact.id, {"email": "other@northwind.example"})

    assert exc.value.status_code == 409
    assert contacts_service.require(db, contact.id).email == "avery.stone@northwind.example"


def test_other_fields_still_save_after_an_email_was_sent(db: Session, contact, clock) -> None:
    add_send(db, contact, clock)

    updated = contacts_service.update(db, contact.id, {"first_name": "Renamed"})

    assert updated.first_name == "Renamed"
    assert updated.email == "avery.stone@northwind.example"


def test_a_duplicate_address_is_refused(db: Session, make_contact, contact) -> None:
    make_contact(email="taken@northwind.example")

    with pytest.raises(AppError) as exc:
        contacts_service.update(db, contact.id, {"email": "Taken@Northwind.example"})

    assert exc.value.status_code == 409
    assert "already in the list" in exc.value.messages[0]
    assert contacts_service.require(db, contact.id).email == "avery.stone@northwind.example"


def test_a_malformed_address_is_refused(db: Session, contact) -> None:
    with pytest.raises(AppError) as exc:
        contacts_service.update(db, contact.id, {"email": "not an email"})

    assert exc.value.status_code == 400
    assert contacts_service.require(db, contact.id).email == "avery.stone@northwind.example"


def test_a_known_address_keeps_its_stored_verdict(db: Session, contact, clock) -> None:
    upsert_validation(
        db,
        "known@northwind.example",
        ValidationResult.valid("mx ok"),
        validator_name="mx",
        now=clock.now(),
    )
    db.commit()

    updated = contacts_service.update(db, contact.id, {"email": "known@northwind.example"})

    assert updated.validation_status == "valid"
    assert updated.validation_detail == "mx ok"
    assert validation_for_email(db, "avery.stone@northwind.example") is None


def test_an_opt_out_stays_on_the_old_address(db: Session, contact, clock) -> None:
    suppressions_service.suppress(
        db, contact.email, reason=REASON_UNSUB, source="link", now=clock.now()
    )
    db.commit()

    updated = contacts_service.update(db, contact.id, {"email": "fixed@northwind.example"})

    assert updated.suppressed is False
    assert suppressions_service.is_suppressed(db, "avery.stone@northwind.example") is not None
    assert suppressions_service.is_suppressed(db, "fixed@northwind.example") is None


def test_send_history_for_one_contact_excludes_everyone_else(
    client, db: Session, make_contact, clock
) -> None:
    """The detail page asks for history with contactId. A missing alias used to
    return every send, which then locked the email field on a contact who had
    never been emailed.
    """
    one = make_contact(email="one@northwind.example")
    two = make_contact(email="two@northwind.example")
    add_send(db, one, clock)
    add_send(db, two, clock)

    response = client.get("/api/v1/sends", params={"contactId": str(one.id)})

    assert response.status_code == 200
    rows = response.json()["data"]
    assert [row["contactId"] for row in rows] == [str(one.id)]


def test_a_suppression_on_the_new_address_follows_the_contact(db: Session, contact, clock) -> None:
    suppressions_service.suppress(
        db,
        "blocked@northwind.example",
        reason=REASON_MANUAL,
        source="manual",
        now=clock.now(),
    )
    db.commit()

    updated = contacts_service.update(db, contact.id, {"email": "blocked@northwind.example"})

    assert updated.suppressed is True
    assert updated.suppressed_reason == REASON_MANUAL
