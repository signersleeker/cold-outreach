"""OAuth callback failure messages.

A failed first API call must never claim the mailbox was connected — nothing is
stored until the profile read succeeds — and the message ends up in a URL query
string, so it has to stay short and actionable.
"""

from __future__ import annotations

import pytest

from app.gmail.exceptions import GmailPermanentError
from app.gmail.oauth_service import (
    google_project_number,
    profile_failure_message,
)

CLIENT_ID = "446044970320-au701um0lrl30bgjh5on3clfn5t7o4ae.apps.googleusercontent.com"

API_DISABLED = GmailPermanentError(
    'GET /profile: HTTP 403: { "error": { "code": 403, "message": "Gmail API has not been '
    'used in project 446044970320 before or it is disabled. Enable it by visiting '
    "https://console.developers.google.com/apis/api/gmail.googleapis.com/overview"
    '?project=446044970320 then retry. If you enabled this API recently, wait a few '
    'minutes for the action to propagate to our systems and retry.", "errors": [ { '
    '"message": "Gmail API has not been used in project 446044970320 before or it is '
    'disabled.", "reason": "accessNotConfigured" } ] } }'
)


def test_project_number_is_read_from_the_client_id() -> None:
    assert google_project_number(CLIENT_ID) == "446044970320"


@pytest.mark.parametrize("client_id", ["", "no-leading-digits.apps.googleusercontent.com"])
def test_project_number_absent_is_handled(client_id: str) -> None:
    assert google_project_number(client_id) == ""


def test_api_not_enabled_gives_a_direct_instruction() -> None:
    message = profile_failure_message(API_DISABLED, CLIENT_ID)
    assert "Gmail API is not enabled" in message
    assert "446044970320" in message, "links straight to the operator's own project"
    assert "console.cloud.google.com/apis/library/gmail.googleapis.com" in message


def test_api_not_enabled_falls_back_without_a_project_number() -> None:
    message = profile_failure_message(API_DISABLED, "")
    assert "APIs & Services" in message
    assert "project=" not in message


def test_failure_never_claims_the_mailbox_was_connected() -> None:
    """The bug this replaced: the banner said "Connected" while status was not_connected."""
    for exc in (
        API_DISABLED,
        GmailPermanentError("HTTP 403: insufficient authentication scopes"),
        GmailPermanentError("invalid_grant"),
        GmailPermanentError("something entirely unexpected"),
    ):
        message = profile_failure_message(exc, CLIENT_ID)
        assert "connected" not in message.lower() or "nothing was connected" in message.lower()


def test_insufficient_scope_is_explained() -> None:
    message = profile_failure_message(
        GmailPermanentError("HTTP 403: Request had insufficient authentication scopes."),
        CLIENT_ID,
    )
    assert "scopes" in message
    assert "myaccount.google.com/permissions" in message


def test_invalid_grant_is_explained() -> None:
    message = profile_failure_message(GmailPermanentError("invalid_grant"), CLIENT_ID)
    assert "authorisation code" in message


def test_unrecognised_errors_are_truncated_for_the_url() -> None:
    message = profile_failure_message(GmailPermanentError("x" * 2000), CLIENT_ID)
    assert len(message) < 400
    assert message.endswith("…")


def test_every_message_is_short_enough_for_a_query_string() -> None:
    for exc in (API_DISABLED, GmailPermanentError("boom"), GmailPermanentError("y" * 5000)):
        assert len(profile_failure_message(exc, CLIENT_ID)) < 400
