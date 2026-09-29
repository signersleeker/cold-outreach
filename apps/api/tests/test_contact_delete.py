"""Deleting a contact.

Two properties matter more than the delete itself: send history is not discarded
silently, and a delete can never become a way to undo an opt-out.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.contacts import service as contacts_service
from app.lib.errors import AppError
from app.sends.constants import SEND_STATUS_SENT
from app.sends.models.send_event import SendEvent
from app.suppressions import service as suppressions_service
from app.suppressions.constants import REASON_UNSUB


def add_send(db: Session, contact, clock) -> SendEvent:
    event = SendEvent(
        contact_id=contact.id,
        template_id=None,
        subject_rendered="shadow AI",
        body_rendered="body",
        rfc822_message_id=f"<{uuid.uuid4()}@kinnatic.ai>",
        status=SEND_STATUS_SENT,
        sent_at=clock.now(),
    )
    db.add(event)
    db.commit()
    return event


# ------------------------------------------------------------- the easy case ----
def test_a_never_emailed_contact_deletes_cleanly(db: Session, contact) -> None:
    result = contacts_service.delete(db, contact.id)

    assert result["deleted"] is True
    assert result["sendEventsDeleted"] == 0
    assert contacts_service.get(db, contact.id) is None


def test_deleting_an_unknown_contact_is_404(db: Session) -> None:
    with pytest.raises(AppError) as exc:
        contacts_service.delete(db, uuid.uuid4())
    assert exc.value.status_code == 404


# ------------------------------------------------------ send history is guarded ----
def test_a_contact_with_send_history_is_refused(db: Session, contact, clock) -> None:
    add_send(db, contact, clock)

    with pytest.raises(AppError) as exc:
        contacts_service.delete(db, contact.id)

    assert exc.value.status_code == 409
    assert "send(s) on record" in exc.value.messages[0]
    assert contacts_service.get(db, contact.id) is not None, "nothing was deleted"


def test_the_refusal_suggests_suppressing_instead(db: Session, contact, clock) -> None:
    add_send(db, contact, clock)
    with pytest.raises(AppError) as exc:
        contacts_service.delete(db, contact.id)
    assert "suppress" in exc.value.messages[0].lower()


def test_force_deletes_the_contact_and_cascades_its_history(
    db: Session, contact, clock
) -> None:
    # Capture the ids up front: after the delete these instances are expired, and
    # reading an attribute would try to refresh a row that no longer exists.
    event_ids = [add_send(db, contact, clock).id for _ in range(2)]
    contact_id = contact.id

    result = contacts_service.delete(db, contact_id, force=True)

    assert result["sendEventsDeleted"] == 2
    assert contacts_service.get(db, contact_id) is None
    # The rows are gone, not merely orphaned.
    assert contacts_service.send_event_count(db, contact_id) == 0
    for event_id in event_ids:
        assert db.get(SendEvent, event_id) is None


def test_force_reports_how_much_history_was_destroyed(db: Session, contact, clock) -> None:
    """The count is returned so the UI can state the cost before and after."""
    for _ in range(3):
        add_send(db, contact, clock)
    assert contacts_service.delete(db, contact.id, force=True)["sendEventsDeleted"] == 3


# ------------------------------------------- deleting must never undo an opt-out ----
def test_deleting_a_contact_leaves_the_suppression_in_place(
    db: Session, contact, clock
) -> None:
    """The decisive property.

    Suppressions are keyed on email in their own table, so removing the contact
    row cannot resurrect someone who unsubscribed.
    """
    email = contact.email
    suppressions_service.suppress(
        db, email, reason=REASON_UNSUB, source="unsub page", now=clock.now()
    )
    db.commit()

    result = contacts_service.delete(db, contact.id)

    assert result["stillSuppressed"] is True
    assert contacts_service.get(db, contact.id) is None
    suppression = suppressions_service.is_suppressed(db, email)
    assert suppression is not None
    assert suppression.reason == REASON_UNSUB


def test_reimporting_a_deleted_opted_out_address_comes_back_suppressed(
    db: Session, contact, clock, validator
) -> None:
    """Delete then re-import must not hand you a clean slate."""
    email = contact.email
    suppressions_service.suppress(
        db, email, reason=REASON_UNSUB, source="unsub page", now=clock.now()
    )
    db.commit()
    contacts_service.delete(db, contact.id)

    summary = contacts_service.import_csv(
        db, f"Email\n{email}\n".encode(), validator=validator, clock=clock
    )

    assert summary.created == 1
    assert summary.suppressed_existing == 1
    recreated = contacts_service.by_email(db, email)
    assert recreated is not None
    assert recreated.suppressed is True
    assert recreated.suppressed_reason == REASON_UNSUB


# ---------------------------------------------------------------- HTTP surface ----
def test_delete_endpoint_removes_an_unsent_contact(client, db: Session, contact) -> None:
    response = client.delete(f"/api/v1/contacts/{contact.id}")
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True
    assert contacts_service.get(db, contact.id) is None


def test_delete_endpoint_409s_on_send_history(client, db: Session, contact, clock) -> None:
    add_send(db, contact, clock)
    response = client.delete(f"/api/v1/contacts/{contact.id}")
    assert response.status_code == 409
    assert contacts_service.get(db, contact.id) is not None


def test_delete_endpoint_accepts_force(client, db: Session, contact, clock) -> None:
    add_send(db, contact, clock)
    response = client.delete(f"/api/v1/contacts/{contact.id}?force=true")
    assert response.status_code == 200
    assert response.json()["data"]["sendEventsDeleted"] == 1
    assert contacts_service.get(db, contact.id) is None


def test_delete_endpoint_requires_a_session(client, contact) -> None:
    client.cookies.clear()
    assert client.delete(f"/api/v1/contacts/{contact.id}").status_code == 401
