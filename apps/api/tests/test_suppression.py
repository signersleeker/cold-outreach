"""Suppression: the do-not-email list, and the inbox signals that populate it."""

from __future__ import annotations

import base64

from sqlalchemy.orm import Session

from app.contacts import service as contacts_service
from app.inbox.parsing import Classification, classify_message, strip_quoted_reply
from app.inbox.service import InboxSyncService
from app.sends.constants import (
    GATE_CONTACT_SUPPRESSED,
    SEND_STATUS_BOUNCED,
    SEND_STATUS_REPLIED_STOP,
    SEND_STATUS_SENT,
)
from app.sends.models.send_event import SendEvent
from app.suppressions import service as suppressions_service
from app.suppressions.constants import (
    REASON_BOUNCE,
    REASON_MANUAL,
    REASON_REPLY_NO,
    REASON_UNSUB,
)
from app.validation.base import ValidationResult


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def payload(
    *, sender: str, subject: str, body: str, headers: dict[str, str] | None = None
) -> dict:
    """A Gmail message payload, as classify_message expects it."""
    all_headers = {"From": sender, "Subject": subject, **(headers or {})}
    return {
        "mimeType": "text/plain",
        "headers": [{"name": k, "value": v} for k, v in all_headers.items()],
        "body": {"data": b64(body)},
    }


def message(**kwargs) -> dict:
    """A full Gmail message, as the API returns it (payload nested)."""
    return {"payload": payload(**kwargs)}


# --------------------------------------------------------------- basic writes ----
def test_manual_suppression_is_recorded(db: Session, clock) -> None:
    row = suppressions_service.suppress(
        db, "Avery@Example.ORG", reason=REASON_MANUAL, source="manual", now=clock.now()
    )
    assert row.email == "avery@example.org", "stored lowercased"
    assert suppressions_service.is_suppressed(db, "AVERY@EXAMPLE.ORG") is not None


def test_suppression_works_for_an_email_with_no_contact_row(db: Session, clock) -> None:
    """Add-before-import is why suppressions is keyed on email, not contact_id."""
    suppressions_service.suppress(
        db, "stranger@example.org", reason=REASON_MANUAL, source="", now=clock.now()
    )
    assert suppressions_service.is_suppressed(db, "stranger@example.org") is not None
    assert contacts_service.by_email(db, "stranger@example.org") is None


def test_suppressing_syncs_the_contact_cache(db: Session, contact, clock) -> None:
    suppressions_service.suppress(
        db, contact.email, reason=REASON_UNSUB, source="", now=clock.now()
    )
    db.flush()
    db.refresh(contact)
    assert contact.suppressed is True
    assert contact.suppressed_reason == REASON_UNSUB
    assert contact.suppressed_at is not None


def test_resuppressing_keeps_the_original_reason(db: Session, contact, clock) -> None:
    """The first opt-out is the one that matters."""
    suppressions_service.suppress(
        db, contact.email, reason=REASON_UNSUB, source="first", now=clock.now()
    )
    again = suppressions_service.suppress(
        db, contact.email, reason=REASON_MANUAL, source="second", now=clock.now()
    )
    assert again.reason == REASON_UNSUB
    assert suppressions_service.count_all(db) == 1


def test_unsuppress_clears_both_table_and_cache(db: Session, contact, clock) -> None:
    suppressions_service.suppress(
        db, contact.email, reason=REASON_UNSUB, source="", now=clock.now()
    )
    db.flush()
    assert suppressions_service.unsuppress(db, contact.email) is True
    db.flush()
    db.refresh(contact)
    assert contact.suppressed is False
    assert contact.suppressed_reason == ""
    assert suppressions_service.is_suppressed(db, contact.email) is None


def test_unsuppress_unknown_email_returns_false(db: Session) -> None:
    assert suppressions_service.unsuppress(db, "nobody@example.org") is False


def test_counts_by_reason(db: Session, clock) -> None:
    for i, reason in enumerate([REASON_UNSUB, REASON_UNSUB, REASON_BOUNCE]):
        suppressions_service.suppress(
            db, f"u{i}@example.org", reason=reason, source="", now=clock.now()
        )
    assert suppressions_service.counts_by_reason(db) == {REASON_UNSUB: 2, REASON_BOUNCE: 1}


# ------------------------------------------------------- import auto-suppression ----
def test_import_auto_suppresses_invalid_addresses(db: Session, validator, clock) -> None:
    validator.by_email = {
        "good@northwind.example": ValidationResult.valid("has MX"),
        "bad@nowhere.invalid": ValidationResult.invalid("no MX record"),
    }
    csv = (
        "Email,First Name,Company,Job Title\n"
        "good@northwind.example,Avery,Northwind,CISO\n"
        "bad@nowhere.invalid,Blake,Nowhere,CTO\n"
    )
    summary = contacts_service.import_csv(
        db, csv.encode(), validator=validator, clock=clock
    )

    assert summary.created == 2
    assert summary.valid == 1
    assert summary.invalid == 1
    assert suppressions_service.is_suppressed(db, "bad@nowhere.invalid") is not None
    assert suppressions_service.is_suppressed(db, "good@northwind.example") is None


def test_revalidate_clears_an_automatic_suppression_when_the_mailbox_exists(
    db: Session, validator, clock
) -> None:
    validator.by_email = {
        "info@clinic.example": ValidationResult.invalid("ZeroBounce: do_not_mail / role_based.")
    }
    contacts_service.import_csv(
        db, b"Email\ninfo@clinic.example\n", validator=validator, clock=clock
    )
    contact = contacts_service.by_email(db, "info@clinic.example")
    assert contact is not None and contact.suppressed is True

    validator.by_email["info@clinic.example"] = ValidationResult.valid(
        "ZeroBounce: do_not_mail / role_based."
    )
    updated = contacts_service.revalidate(db, contact.id, validator=validator, clock=clock)

    assert updated.validation_status == "valid"
    assert updated.suppressed is False
    assert suppressions_service.is_suppressed(db, "info@clinic.example") is None


def test_revalidate_leaves_an_opt_out_in_place(db: Session, validator, clock) -> None:
    suppressions_service.suppress(
        db, "info@clinic.example", reason=REASON_UNSUB, source="reply", now=clock.now()
    )
    db.flush()
    contacts_service.import_csv(
        db, b"Email\ninfo@clinic.example\n", validator=validator, clock=clock
    )
    contact = contacts_service.by_email(db, "info@clinic.example")
    assert contact is not None

    updated = contacts_service.revalidate(db, contact.id, validator=validator, clock=clock)

    assert updated.validation_status == "valid"
    assert updated.suppressed is True
    assert updated.suppressed_reason == REASON_UNSUB


def test_import_marks_risky_without_suppressing(db: Session, validator, clock) -> None:
    validator.default = ValidationResult.risky("catch-all domain")
    summary = contacts_service.import_csv(
        db, b"Email\nrisky@catchall.example\n", validator=validator, clock=clock
    )
    assert summary.risky == 1
    assert suppressions_service.is_suppressed(db, "risky@catchall.example") is None


def test_import_does_not_resurrect_an_opted_out_address(
    db: Session, validator, clock
) -> None:
    """Re-uploading a CSV must never undo an opt-out."""
    suppressions_service.suppress(
        db, "avery@northwind.example", reason=REASON_UNSUB, source="", now=clock.now()
    )
    db.flush()

    summary = contacts_service.import_csv(
        db, b"Email\navery@northwind.example\n", validator=validator, clock=clock
    )
    assert summary.created == 1
    assert summary.suppressed_existing == 1

    contact = contacts_service.by_email(db, "avery@northwind.example")
    assert contact is not None
    assert contact.suppressed is True
    assert contact.suppressed_reason == REASON_UNSUB
    suppression = suppressions_service.is_suppressed(db, "avery@northwind.example")
    assert suppression is not None and suppression.reason == REASON_UNSUB


def test_import_skips_duplicates_against_existing_contacts(
    db: Session, contact, validator, clock
) -> None:
    summary = contacts_service.import_csv(
        db, f"Email\n{contact.email.upper()}\n".encode(), validator=validator, clock=clock
    )
    assert summary.created == 0
    assert summary.skipped_dupes == 1


def test_validation_failure_leaves_the_row_pending(db: Session, validator, clock) -> None:
    class Exploding:
        name = "exploding"

        def validate(self, email: str):
            raise RuntimeError("DNS is down")

    summary = contacts_service.import_csv(
        db, b"Email\navery@northwind.example\n", validator=Exploding(), clock=clock
    )
    assert summary.created == 1
    assert summary.pending == 1
    contact = contacts_service.by_email(db, "avery@northwind.example")
    assert contact is not None and contact.validation_status == "pending"


# ---------------------------------------------- a suppressed contact cannot be sent ----
def test_suppressed_contact_is_blocked_from_sending(
    db: Session, contact, template, app_settings, connected_gmail, send_service, clock
) -> None:
    preview = send_service.preview(
        db, contact_id=contact.id, template_id=template.id
    )
    assert preview.result.ok is True, "sendable before suppression"

    suppressions_service.suppress(
        db, contact.email, reason=REASON_UNSUB, source="", now=clock.now()
    )
    db.flush()

    blocked = send_service.preview(db, contact_id=contact.id, template_id=template.id)
    assert blocked.result.ok is False
    assert GATE_CONTACT_SUPPRESSED in {f.code for f in blocked.result.blockers}


def test_gate_reads_the_suppressions_table_not_the_contact_cache(
    db: Session, contact, template, app_settings, connected_gmail, send_service, clock
) -> None:
    """A stale cache must not let a suppressed address through."""
    suppressions_service.suppress(
        db, contact.email, reason=REASON_UNSUB, source="", now=clock.now()
    )
    contact.suppressed = False  # deliberately desynchronise the cache
    contact.suppressed_reason = ""
    db.add(contact)
    db.flush()

    preview = send_service.preview(db, contact_id=contact.id, template_id=template.id)
    assert GATE_CONTACT_SUPPRESSED in {f.code for f in preview.result.blockers}


# ------------------------------------------------------------ quoted-reply guard ----
def test_stop_words_in_quoted_text_are_ignored() -> None:
    """Our own footer says reply "no" — a quoted thread must not trip the matcher."""
    body = (
        "Thanks, this is genuinely interesting. Let's talk next week.\n\n"
        "On Mon, 2 Mar 2026 at 10:00, Joey <joey@kinnatic.ai> wrote:\n"
        "> Hi Avery,\n"
        "> If this isn't relevant, reply \"no\" and I won't email again.\n"
        "> Also you might not be interested, just say stop.\n"
    )
    assert "not interested" not in strip_quoted_reply(body)
    parsed = classify_message(
        payload(sender="Avery <avery@northwind.example>", subject="Re: shadow AI", body=body)
    )
    assert parsed.classification is Classification.REPLY_OTHER


def test_original_message_marker_also_cuts_the_quote() -> None:
    body = "Sure, happy to chat.\n\n-----Original Message-----\nreply \"no\" to stop\n"
    assert "stop" not in strip_quoted_reply(body)


def test_a_genuine_stop_reply_is_detected() -> None:
    parsed = classify_message(
        payload(
            sender="Avery <avery@northwind.example>",
            subject="Re: shadow AI",
            body="Not interested, please remove me.\n\nOn Mon Joey wrote:\n> original\n",
        )
    )
    assert parsed.classification is Classification.REPLY_STOP
    assert parsed.from_email == "avery@northwind.example"


def test_bare_no_reply_is_detected_via_stop_phrases() -> None:
    parsed = classify_message(
        payload(sender="a@northwind.example", subject="Re: x", body="No thanks.")
    )
    assert parsed.classification is Classification.REPLY_STOP


def test_stop_word_in_the_subject_is_honoured() -> None:
    parsed = classify_message(
        payload(sender="a@northwind.example", subject="Unsubscribe", body="")
    )
    assert parsed.classification is Classification.REPLY_STOP


def test_out_of_office_is_classified_as_an_auto_reply() -> None:
    parsed = classify_message(
        payload(
            sender="a@northwind.example",
            subject="Automatic reply: Out of office",
            body="I am on leave and not interested in email until March.",
        )
    )
    assert parsed.classification is Classification.AUTO_REPLY, "must not suppress"


# ------------------------------------------------------------------- bounces ----
def hard_bounce(recipient: str) -> dict:
    return {
        "payload": {
            "mimeType": "multipart/report",
            "headers": [
                {"name": "From", "value": "Mail Delivery Subsystem <mailer-daemon@googlemail.com>"},
                {"name": "Subject", "value": "Delivery Status Notification (Failure)"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": b64("Address not found.")},
                },
                {
                    "mimeType": "message/delivery-status",
                    "body": {
                        "data": b64(
                            f"Final-Recipient: rfc822; {recipient}\n"
                            "Action: failed\n"
                            "Status: 5.1.1\n"
                        )
                    },
                },
            ],
        }
    }


def soft_bounce(recipient: str) -> dict:
    return {
        "payload": {
            "mimeType": "multipart/report",
            "headers": [
                {"name": "From", "value": "mailer-daemon@googlemail.com"},
                {"name": "Subject", "value": "Delivery Status Notification (Delay)"},
            ],
            "parts": [
                {
                    "mimeType": "message/delivery-status",
                    "body": {
                        "data": b64(
                            f"Final-Recipient: rfc822; {recipient}\n"
                            "Action: delayed\n"
                            "Status: 4.2.2\n"
                        )
                    },
                },
            ],
        }
    }


def test_permanent_bounce_is_classified_and_names_the_recipient() -> None:
    parsed = classify_message(hard_bounce("avery@northwind.example")["payload"])
    assert parsed.classification is Classification.BOUNCE_PERMANENT
    assert parsed.affected_email == "avery@northwind.example"


def test_soft_bounce_is_classified_separately() -> None:
    parsed = classify_message(soft_bounce("avery@northwind.example")["payload"])
    assert parsed.classification is Classification.BOUNCE_SOFT


def test_x_failed_recipients_header_is_preferred() -> None:
    payload = hard_bounce("from-body@example.org")["payload"]
    payload["headers"].append(
        {"name": "X-Failed-Recipients", "value": "from-header@example.org"}
    )
    assert classify_message(payload).affected_email == "from-header@example.org"


# -------------------------------------------------------------- inbox sync ----
def sent_contact(db: Session, make_contact, clock, email: str):
    contact = make_contact(email=email, last_sent_at=clock.now())
    event = SendEvent(
        contact_id=contact.id,
        template_id=None,
        subject_rendered="shadow AI",
        body_rendered="body",
        rfc822_message_id="<abc@kinnatic.ai>",
        status=SEND_STATUS_SENT,
        sent_at=clock.now(),
    )
    db.add(event)
    db.flush()
    return contact, event


def test_sync_suppresses_a_stop_reply(db: Session, make_contact, clock, gmail) -> None:
    contact, event = sent_contact(db, make_contact, clock, "avery@northwind.example")
    gmail.listings = {
        q: ["m1"]
        for q in [f"in:inbox newer_than:30d (from:{contact.email})"]
    }
    gmail.messages = {
        "m1": message(
            sender=f"Avery <{contact.email}>",
            subject="Re: shadow AI",
            body="Not interested, thanks.",
        )
    }

    summary = InboxSyncService(clock).sync(db, gmail)
    assert summary.stops_found == 1
    assert summary.suppressed == 1

    suppression = suppressions_service.is_suppressed(db, contact.email)
    assert suppression is not None and suppression.reason == REASON_REPLY_NO
    db.refresh(event)
    assert event.status == SEND_STATUS_REPLIED_STOP


def test_sync_suppresses_a_permanent_bounce(db: Session, make_contact, clock, gmail) -> None:
    contact, event = sent_contact(db, make_contact, clock, "avery@northwind.example")
    gmail.listings = {}
    gmail.stage_inbox(
        __import__("app.inbox.service", fromlist=["_BOUNCE_QUERY"])._BOUNCE_QUERY,
        {"b1": hard_bounce(contact.email)},
    )

    summary = InboxSyncService(clock).sync(db, gmail)
    assert summary.bounces_found == 1
    suppression = suppressions_service.is_suppressed(db, contact.email)
    assert suppression is not None and suppression.reason == REASON_BOUNCE
    db.refresh(event)
    assert event.status == SEND_STATUS_BOUNCED


def test_sync_does_not_suppress_a_soft_bounce(db: Session, make_contact, clock, gmail) -> None:
    """The most consequential inbox-sync bug to avoid."""
    contact, event = sent_contact(db, make_contact, clock, "avery@northwind.example")
    gmail.stage_inbox(
        __import__("app.inbox.service", fromlist=["_BOUNCE_QUERY"])._BOUNCE_QUERY,
        {"b1": soft_bounce(contact.email)},
    )

    summary = InboxSyncService(clock).sync(db, gmail)
    assert summary.soft_bounces == 1
    assert summary.suppressed == 0
    assert suppressions_service.is_suppressed(db, contact.email) is None
    db.refresh(event)
    assert event.status == SEND_STATUS_SENT, "status is untouched by a deferral"


def test_sync_ignores_a_stop_reply_from_a_stranger(
    db: Session, make_contact, clock, gmail
) -> None:
    """Only addresses we actually emailed can be suppressed by a sync."""
    sent_contact(db, make_contact, clock, "avery@northwind.example")
    gmail.listings = {
        "in:inbox newer_than:30d (from:avery@northwind.example)": ["m1"]
    }
    gmail.messages = {
        "m1": message(sender="spam@elsewhere.example", subject="stop", body="unsubscribe")
    }

    summary = InboxSyncService(clock).sync(db, gmail)
    assert summary.suppressed == 0
    assert suppressions_service.is_suppressed(db, "spam@elsewhere.example") is None


def test_sync_records_the_timestamp(db: Session, clock, gmail, app_settings) -> None:
    InboxSyncService(clock).sync(db, gmail)
    db.refresh(app_settings)
    assert app_settings.last_inbox_sync_at == clock.now()
