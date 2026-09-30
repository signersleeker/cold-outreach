"""The send path: gates, the reserve/settle choreography, and MIME output."""

from __future__ import annotations

import base64
import datetime as dt
from email import message_from_bytes

import pytest
from sqlalchemy.orm import Session

from app.gmail.constants import FORBIDDEN_HEADERS
from app.lib.clock import DEFAULT_TIMEZONE, local_date
from app.lib.errors import AppError
from app.sends.constants import (
    GATE_COOLDOWN_ACTIVE,
    GATE_DAILY_CAP_REACHED,
    GATE_GMAIL_NOT_CONNECTED,
    GATE_UNRENDERED_MERGE_TAGS,
    GATE_VALIDATION_RISKY,
    SEND_STATUS_FAILED,
    SEND_STATUS_QUEUED,
    SEND_STATUS_SENT,
)
from app.sends.services import counters
from app.sends.services.compose import format_unsub_line
from app.templates.constants import OPT_OUT_SENTENCE


def decode_sent(raw: str):
    padded = raw + "=" * (-len(raw) % 4)
    return message_from_bytes(base64.urlsafe_b64decode(padded))


def body_of(msg) -> str:
    """The decoded text/plain body.

    set_content appends the trailing newline RFC 5322 requires, so this is the
    stored body plus one "\\n"; callers comparing against stored text strip it.
    """
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.is_multipart():
                payload = part.get_payload(decode=True)
                return payload.decode("utf-8") if payload else ""
    payload = msg.get_payload(decode=True)
    return payload.decode("utf-8") if payload else ""


def html_of(msg) -> str:
    """The decoded text/html alternative, if present."""
    if not msg.is_multipart():
        return ""
    for part in msg.walk():
        if part.get_content_type() == "text/html" and not part.is_multipart():
            payload = part.get_payload(decode=True)
            return payload.decode("utf-8") if payload else ""
    return ""


# ------------------------------------------------------------------- preview ----
def test_preview_renders_the_exact_body_that_will_be_sent(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    preview = send_service.preview(db, contact_id=contact.id, template_id=template.id)
    assert preview.result.ok is True

    send_service.send(db, contact_id=contact.id, template_id=template.id)
    sent = body_of(decode_sent(gmail.sent_raw[0]))

    assert sent.rstrip("\n") == preview.body.rstrip("\n")
    assert sent == preview.body + "\n", "the only difference is the RFC trailing newline"


def test_preview_does_not_consume_a_slot(
    db: Session, contact, template, app_settings, connected_gmail, send_service, clock
) -> None:
    for _ in range(3):
        send_service.preview(db, contact_id=contact.id, template_id=template.id)
    assert counters.sends_today(db, local_date(clock, DEFAULT_TIMEZONE)) == 0


def test_preview_reports_blockers_without_raising(
    db: Session, contact, template, app_settings, send_service
) -> None:
    """No connected_gmail fixture, so the mailbox is not connected."""
    preview = send_service.preview(db, contact_id=contact.id, template_id=template.id)
    assert preview.result.ok is False
    assert GATE_GMAIL_NOT_CONNECTED in {f.code for f in preview.result.blockers}


def test_preview_of_a_missing_contact_raises_404(
    db: Session, template, app_settings, send_service
) -> None:
    import uuid

    with pytest.raises(AppError) as exc:
        send_service.preview(db, contact_id=uuid.uuid4(), template_id=template.id)
    assert exc.value.status_code == 404


# ---------------------------------------------------------------- happy path ----
def test_send_records_the_gmail_message_id_and_moves_the_counter(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail, clock
) -> None:
    gmail.next_message_id = "gmail-abc-123"
    event = send_service.send(db, contact_id=contact.id, template_id=template.id)

    assert event.status == SEND_STATUS_SENT
    assert event.gmail_message_id == "gmail-abc-123"
    assert event.sent_at == clock.now()
    assert counters.sends_today(db, local_date(clock, DEFAULT_TIMEZONE)) == 1
    assert len(gmail.sent_raw) == 1


def test_send_stamps_last_sent_at_on_the_contact(
    db: Session, contact, template, app_settings, connected_gmail, send_service, clock
) -> None:
    send_service.send(db, contact_id=contact.id, template_id=template.id)
    db.refresh(contact)
    assert contact.last_sent_at == clock.now()


def test_send_archives_the_exact_rendered_body(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    event = send_service.send(db, contact_id=contact.id, template_id=template.id)
    sent = body_of(decode_sent(gmail.sent_raw[0]))
    assert sent.rstrip("\n") == event.body_rendered.rstrip("\n")


# ------------------------------------------------------------------- gating ----
def test_send_refuses_when_gmail_is_not_connected(
    db: Session, contact, template, app_settings, send_service, gmail, clock
) -> None:
    with pytest.raises(AppError) as exc:
        send_service.send(db, contact_id=contact.id, template_id=template.id)
    assert exc.value.status_code == 422
    assert gmail.sent_raw == [], "nothing may leave before the gates pass"
    assert counters.sends_today(db, local_date(clock, DEFAULT_TIMEZONE)) == 0


def test_cooldown_blocks_an_immediate_resend(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    send_service.send(db, contact_id=contact.id, template_id=template.id)

    with pytest.raises(AppError) as exc:
        send_service.send(db, contact_id=contact.id, template_id=template.id)
    assert any("Already emailed" in m for m in exc.value.messages)
    assert len(gmail.sent_raw) == 1


def test_resend_is_allowed_once_the_cooldown_expires(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail, clock
) -> None:
    send_service.send(db, contact_id=contact.id, template_id=template.id)
    clock.advance(days=15)
    send_service.send(db, contact_id=contact.id, template_id=template.id)
    assert len(gmail.sent_raw) == 2


def test_missing_merge_field_blocks_the_send(
    db: Session, make_contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    """The seeded template references {{company}}; this contact has none."""
    contact = make_contact(email="nocompany@northwind.example", company="")

    preview = send_service.preview(db, contact_id=contact.id, template_id=template.id)
    assert GATE_UNRENDERED_MERGE_TAGS in {f.code for f in preview.result.blockers}

    with pytest.raises(AppError):
        send_service.send(db, contact_id=contact.id, template_id=template.id)
    assert gmail.sent_raw == []


def test_risky_contact_needs_acknowledgement(
    db: Session, make_contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    contact = make_contact(email="risky@catchall.example", validation_status="risky")

    with pytest.raises(AppError):
        send_service.send(db, contact_id=contact.id, template_id=template.id)
    assert gmail.sent_raw == []

    event = send_service.send(
        db,
        contact_id=contact.id,
        template_id=template.id,
        acknowledge=frozenset({GATE_VALIDATION_RISKY}),
    )
    assert event.status == SEND_STATUS_SENT


def test_invalid_contact_cannot_be_sent_even_with_acknowledgement(
    db: Session, make_contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    contact = make_contact(email="bad@nowhere.invalid", validation_status="invalid")
    with pytest.raises(AppError):
        send_service.send(
            db,
            contact_id=contact.id,
            template_id=template.id,
            acknowledge=frozenset({GATE_VALIDATION_RISKY, "email_invalid"}),
        )
    assert gmail.sent_raw == []


# ----------------------------------------------------------------- daily cap ----
def test_the_cap_stops_sending(
    db: Session, make_contact, template, app_settings, connected_gmail, send_service, gmail, clock
) -> None:
    app_settings.daily_cap = 3
    db.add(app_settings)
    db.commit()

    contacts = [make_contact(email=f"p{i}@northwind.example") for i in range(5)]
    sent = 0
    for contact in contacts:
        try:
            send_service.send(db, contact_id=contact.id, template_id=template.id)
            sent += 1
        except AppError as exc:
            assert GATE_DAILY_CAP_REACHED in str(exc.messages) or "Daily cap" in str(exc.messages)

    assert sent == 3
    assert len(gmail.sent_raw) == 3
    assert counters.sends_today(db, local_date(clock, DEFAULT_TIMEZONE)) == 3


def test_the_cap_is_clamped_to_the_server_ceiling(
    db: Session, app_settings, send_service
) -> None:
    from app.app_settings import service as settings_service
    from app.constants import HARD_MAX_DAILY_CAP

    app_settings.daily_cap = 5000
    db.add(app_settings)
    db.commit()
    assert settings_service.effective_daily_cap(db) == HARD_MAX_DAILY_CAP


def test_the_cap_resets_on_the_next_calendar_day(
    db: Session, make_contact, template, app_settings, connected_gmail, send_service, gmail, clock
) -> None:
    app_settings.daily_cap = 1
    db.add(app_settings)
    db.commit()

    send_service.send(
        db, contact_id=make_contact(email="a@northwind.example").id, template_id=template.id
    )
    with pytest.raises(AppError):
        send_service.send(
            db, contact_id=make_contact(email="b@northwind.example").id, template_id=template.id
        )

    clock.advance(days=1)
    send_service.send(
        db, contact_id=make_contact(email="c@northwind.example").id, template_id=template.id
    )
    assert len(gmail.sent_raw) == 2


# ------------------------------------------------------- failure compensation ----
def test_permanent_gmail_failure_releases_the_slot_and_undoes_the_cooldown(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail, clock
) -> None:
    """Gmail rejected it outright, so it was never queued."""
    gmail.fail_permanent = True

    with pytest.raises(AppError) as exc:
        send_service.send(db, contact_id=contact.id, template_id=template.id)
    assert exc.value.status_code == 502

    assert counters.sends_today(db, local_date(clock, DEFAULT_TIMEZONE)) == 0, "slot returned"
    db.refresh(contact)
    assert contact.last_sent_at is None, "cooldown stamp rolled back"

    events = send_service.history(db, contact_id=contact.id)
    assert events[0].status == SEND_STATUS_FAILED
    assert events[0].error


def test_a_retry_after_a_permanent_failure_is_allowed(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    gmail.fail_permanent = True
    with pytest.raises(AppError):
        send_service.send(db, contact_id=contact.id, template_id=template.id)

    gmail.fail_permanent = False
    event = send_service.send(db, contact_id=contact.id, template_id=template.id)
    assert event.status == SEND_STATUS_SENT


def test_ambiguous_gmail_failure_keeps_the_slot_consumed(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail, clock
) -> None:
    """A timeout may mean it did go out. Under-send rather than risk a double send."""
    gmail.fail_ambiguous = True

    with pytest.raises(AppError) as exc:
        send_service.send(db, contact_id=contact.id, template_id=template.id)
    assert exc.value.status_code == 504

    assert counters.sends_today(db, local_date(clock, DEFAULT_TIMEZONE)) == 1, "slot deliberately retained"
    db.refresh(contact)
    assert contact.last_sent_at is not None, "cooldown deliberately retained"


def test_ambiguous_failure_leaves_a_retryable_cooldown_block(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    """The operator must check Gmail rather than blindly retry."""
    gmail.fail_ambiguous = True
    with pytest.raises(AppError):
        send_service.send(db, contact_id=contact.id, template_id=template.id)

    gmail.fail_ambiguous = False
    preview = send_service.preview(db, contact_id=contact.id, template_id=template.id)
    assert GATE_COOLDOWN_ACTIVE in {f.code for f in preview.result.blockers}


def test_a_queued_event_is_reported_as_stuck(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail, clock
) -> None:
    """An interrupted send leaves a durable record the dashboard can surface."""
    from app.sends.models.send_event import SendEvent

    db.add(
        SendEvent(
            contact_id=contact.id,
            template_id=template.id,
            subject_rendered="s",
            body_rendered="b",
            rfc822_message_id="<stuck@kinnatic.ai>",
            status=SEND_STATUS_QUEUED,
            created_at=clock.now() - dt.timedelta(minutes=30),
        )
    )
    db.flush()
    assert len(send_service.stuck_queued(db)) == 1


# ------------------------------------------------------------ the MIME output ----
def test_sent_message_is_multipart_alternative_with_html_signature(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    send_service.send(db, contact_id=contact.id, template_id=template.id)
    msg = decode_sent(gmail.sent_raw[0])

    assert msg.get_content_type() == "multipart/alternative"
    assert msg.is_multipart() is True
    plain = body_of(msg)
    html = html_of(msg)
    assert "Joey" in plain
    assert "kinnatic.ai" in plain
    assert "<b>Joey</b>" in html or "<b>Joey</b>" in gmail.signature_html
    assert gmail.signature_html.strip() in html
    assert "text/html" in msg.as_string().lower()


def test_sent_message_carries_no_bulk_headers(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    """The machine-checkable form of "this is not a blast tool"."""
    send_service.send(db, contact_id=contact.id, template_id=template.id)
    msg = decode_sent(gmail.sent_raw[0])

    present = {key.lower() for key in msg}
    assert FORBIDDEN_HEADERS & present == set()
    # multipart/alternative adds MIME-Version on the outer message; parts carry
    # their own Content-Type / Content-Transfer-Encoding.
    assert "list-unsubscribe" not in present


def test_no_tracking_markers_in_the_raw_bytes(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    gmail.signature_html = "<div>Joey<br>Kinnatic</div>"
    send_service.send(db, contact_id=contact.id, template_id=template.id)
    encoded = gmail.sent_raw[0]
    raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()

    lowered = raw.lower()
    assert 'src="http' not in lowered, "no remote tracking pixel of our own"
    for header in ("list-unsubscribe", "list-id", "precedence", "x-mailer"):
        assert header not in lowered


def test_from_and_reply_to_are_the_connected_mailbox(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    send_service.send(db, contact_id=contact.id, template_id=template.id)
    msg = decode_sent(gmail.sent_raw[0])

    assert msg["From"] == "Joey <joey@kinnatic.ai>"
    assert msg["Reply-To"] == "Joey <joey@kinnatic.ai>"
    assert msg["To"] == "Avery Stone <avery.stone@northwind.example>"


def test_body_ends_with_opt_out_then_the_unsub_line(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail, settings
) -> None:
    send_service.send(db, contact_id=contact.id, template_id=template.id)
    body = body_of(decode_sent(gmail.sent_raw[0]))

    expected_url = settings.unsub_url(contact.unsub_token)
    assert body.splitlines()[-1] == format_unsub_line(expected_url)
    assert body.count(expected_url) == 1
    assert body.count(OPT_OUT_SENTENCE) == 1
    # Plain identity block is gone; company name may still appear in the signature.
    assert "CEO\nKinnatic Pty Ltd\n" not in body

    html = html_of(decode_sent(gmail.sent_raw[0]))
    assert f'<a href="{expected_url}">Unsubscribe</a>' in html


def test_unsub_link_omitted_when_setting_is_off(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail, settings
) -> None:
    app_settings.include_unsub_link = False
    db.add(app_settings)
    db.commit()

    send_service.send(db, contact_id=contact.id, template_id=template.id)
    body = body_of(decode_sent(gmail.sent_raw[0]))
    html = html_of(decode_sent(gmail.sent_raw[0]))
    expected_url = settings.unsub_url(contact.unsub_token)

    assert expected_url not in body
    assert "Unsubscribe" not in body
    assert expected_url not in html
    assert body.count(OPT_OUT_SENTENCE) == 1


def test_gmail_display_name_wins_over_stored_sender_name(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    gmail.display_name = "Joseph from Gmail"
    app_settings.sender_name = "Stored Joey"
    db.add(app_settings)
    db.commit()

    send_service.send(db, contact_id=contact.id, template_id=template.id)
    msg = decode_sent(gmail.sent_raw[0])
    assert msg["From"] == "Joseph from Gmail <joey@kinnatic.ai>"


def test_non_ascii_recipient_name_is_rfc2047_encoded(
    db: Session, make_contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    contact = make_contact(
        email="e.laurent@kestrel.example", first_name="Élodie", last_name="Laurent"
    )
    send_service.send(db, contact_id=contact.id, template_id=template.id)
    raw = base64.urlsafe_b64decode(
        gmail.sent_raw[0] + "=" * (-len(gmail.sent_raw[0]) % 4)
    ).decode("ascii", errors="strict")
    assert "=?utf-8?" in raw.lower(), "header is encoded, not raw UTF-8 bytes"

    msg = decode_sent(gmail.sent_raw[0])
    from email.header import decode_header, make_header

    assert "Élodie" in str(make_header(decode_header(msg["To"])))


def test_message_id_is_generated_before_the_send_and_persisted(
    db: Session, contact, template, app_settings, connected_gmail, send_service, gmail
) -> None:
    """This is what makes an interrupted send reconcilable."""
    event = send_service.send(db, contact_id=contact.id, template_id=template.id)
    msg = decode_sent(gmail.sent_raw[0])
    assert event.rfc822_message_id
    assert msg["Message-ID"] == event.rfc822_message_id
    assert "kinnatic.ai" in event.rfc822_message_id
