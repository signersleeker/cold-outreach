"""Unsubscribe tokens and the public unsubscribe page."""

from __future__ import annotations

import base64

from sqlalchemy.orm import Session

from app.contacts import service as contacts_service
from app.contacts.service import new_unsub_token
from app.suppressions import service as suppressions_service
from app.suppressions.constants import REASON_UNSUB


# ------------------------------------------------------------------- the token ----
def test_token_has_256_bits_of_entropy() -> None:
    token = new_unsub_token()
    padded = token + "=" * (-len(token) % 4)
    assert len(base64.urlsafe_b64decode(padded)) == 32


def test_token_is_url_safe() -> None:
    for _ in range(50):
        token = new_unsub_token()
        assert "/" not in token and "+" not in token and "=" not in token


def test_tokens_are_unique_across_many_generations() -> None:
    assert len({new_unsub_token() for _ in range(2000)}) == 2000


def test_token_does_not_encode_the_email(make_contact) -> None:
    """A leaked link must not disclose the address it belongs to."""
    contact = make_contact(email="avery.stone@northwind.example")
    assert "avery" not in contact.unsub_token.lower()
    assert "northwind" not in contact.unsub_token.lower()


def test_each_contact_gets_a_distinct_token(make_contact) -> None:
    tokens = {make_contact(email=f"user{i}@example.org").unsub_token for i in range(25)}
    assert len(tokens) == 25


# ------------------------------------------------------------------- lookup ----
def test_lookup_by_token_finds_exactly_one_contact(db: Session, make_contact) -> None:
    contact = make_contact(email="avery@northwind.example")
    make_contact(email="other@northwind.example")

    found = contacts_service.by_unsub_token(db, contact.unsub_token)
    assert found is not None
    assert found.id == contact.id
    assert found.email == "avery@northwind.example"


def test_unknown_token_returns_none(db: Session, contact) -> None:
    assert contacts_service.by_unsub_token(db, new_unsub_token()) is None


def test_empty_token_returns_none_without_a_query(db: Session) -> None:
    assert contacts_service.by_unsub_token(db, "") is None


def test_token_survives_an_email_correction(db: Session, contact) -> None:
    """Binding is by row identity, so fixing a typo does not invalidate the link."""
    original = contact.unsub_token
    contact.email = "corrected@northwind.example"
    db.add(contact)
    db.flush()

    found = contacts_service.by_unsub_token(db, original)
    assert found is not None
    assert found.email == "corrected@northwind.example"


# -------------------------------------------------------------- the public page ----
def test_get_renders_a_confirmation_and_does_not_suppress(
    client, db: Session, contact, app_settings
) -> None:
    """A GET must be safe: mail scanners prefetch links in received email."""
    response = client.get(f"/u/{contact.unsub_token}")
    assert response.status_code == 200
    assert "unsubscribe" in response.text.lower()
    assert contact.email in response.text
    assert f'action="/u/{contact.unsub_token}"' in response.text
    assert suppressions_service.is_suppressed(db, contact.email) is None, "GET is read-only"


def test_get_requires_no_session(client, contact, app_settings) -> None:
    client.cookies.clear()
    assert client.get(f"/u/{contact.unsub_token}").status_code == 200


def test_post_suppresses_the_contact(client, db: Session, contact, app_settings) -> None:
    response = client.post(f"/u/{contact.unsub_token}")
    assert response.status_code == 200
    assert "unsubscribed" in response.text.lower()

    suppression = suppressions_service.is_suppressed(db, contact.email)
    assert suppression is not None
    assert suppression.reason == REASON_UNSUB

    db.refresh(contact)
    assert contact.suppressed is True
    assert contact.suppressed_reason == REASON_UNSUB


def test_post_requires_no_session(client, db: Session, contact, app_settings) -> None:
    client.cookies.clear()
    assert client.post(f"/u/{contact.unsub_token}").status_code == 200
    assert suppressions_service.is_suppressed(db, contact.email) is not None


def test_post_is_idempotent(client, db: Session, contact, app_settings) -> None:
    first = client.post(f"/u/{contact.unsub_token}")
    second = client.post(f"/u/{contact.unsub_token}")
    assert first.status_code == second.status_code == 200
    assert suppressions_service.count_all(db) == 1


def test_unknown_token_is_not_an_enumeration_oracle(client, app_settings) -> None:
    """Unknown and malformed tokens render the same page, with the same status."""
    unknown = client.get(f"/u/{new_unsub_token()}")
    malformed = client.get("/u/not-a-real-token")
    assert unknown.status_code == malformed.status_code == 200
    assert unknown.text == malformed.text
    assert "no longer valid" in unknown.text.lower()


def test_already_suppressed_token_shows_the_done_page(
    client, db: Session, contact, app_settings, clock
) -> None:
    suppressions_service.suppress(
        db, contact.email, reason=REASON_UNSUB, source="test", now=clock.now()
    )
    db.flush()
    response = client.get(f"/u/{contact.unsub_token}")
    assert "unsubscribed" in response.text.lower()
    assert "<form" not in response.text, "nothing left to confirm"


def test_page_is_marked_noindex(client, contact, app_settings) -> None:
    assert 'name="robots"' in client.get(f"/u/{contact.unsub_token}").text


def test_page_carries_no_javascript_or_external_resources(
    client, contact, app_settings
) -> None:
    body = client.get(f"/u/{contact.unsub_token}").text
    assert "<script" not in body.lower()
    assert "http://" not in body.replace('action="/u/', ""), "no external resources"


def test_email_is_html_escaped(client, db: Session, make_contact, app_settings) -> None:
    contact = make_contact(email="a+<script>@example.org", validation_status="risky")
    body = client.get(f"/u/{contact.unsub_token}").text
    assert "<script>" not in body
    assert "&lt;script&gt;" in body
