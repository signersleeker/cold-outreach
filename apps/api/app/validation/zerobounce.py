"""ZeroBounce validation, used when ZEROBOUNCE_API_KEY is set.

https://www.zerobounce.net/docs/email-validation-api-quickstart/
"""

from __future__ import annotations

import httpx

from app.contacts.normalize import is_valid_syntax
from app.validation.base import ValidationResult

ZEROBOUNCE_VALIDATE_URL = "https://api.zerobounce.net/v2/validate"

_TIMEOUT_SECONDS = 15.0

# ZeroBounce "status" -> our vocabulary, before sub_status is considered.
# catch-all accepts every address, so the specific mailbox is unconfirmed.
# do_not_mail is a mix: role inboxes exist, and the rest should not be mailed.
_STATUS_MAP = {
    "valid": "valid",
    "invalid": "invalid",
    "catch-all": "risky",
    "spamtrap": "invalid",
    "abuse": "invalid",
    "do_not_mail": "invalid",
    "unknown": "unknown",
}

# ZeroBounce files these under do_not_mail, and documents them as real mailboxes
# (info@, admin@, reception@). https://www.zerobounce.net/docs/email-validation-api-quickstart/v2-status-codes
_MAILBOX_EXISTS = frozenset({"role_based"})

# The address cannot receive mail.
_MAILBOX_ABSENT = frozenset(
    {
        "mailbox_not_found",
        "no_dns_entries",
        "does_not_accept_mail",
        "failed_syntax_check",
        "possible_typo",
        "unroutable_ip_address",
    }
)

# A role-shaped address on a domain that accepts every recipient. The specific
# mailbox was not confirmed, so this is not "valid" and not "invalid".
_MAILBOX_UNCONFIRMED = frozenset({"role_based_catch_all", "role_based_accept_all"})

# Real or not, these must not be mailed.
_DO_NOT_SEND = frozenset(
    {"disposable", "toxic", "global_suppression", "possible_trap", "spamtrap", "abuse"}
)


def verdict(raw_status: str, sub_status: str) -> str:
    """Map a ZeroBounce result to valid, invalid, risky, or unknown.

    valid: the mailbox exists. invalid: it does not, or it must not be mailed.
    risky: this specific mailbox could not be confirmed. unknown: the check
    did not finish.
    """
    if sub_status in _DO_NOT_SEND or raw_status in _DO_NOT_SEND:
        return "invalid"
    if sub_status in _MAILBOX_EXISTS:
        return "valid"
    if sub_status in _MAILBOX_UNCONFIRMED or raw_status == "catch-all":
        return "risky"
    if raw_status == "invalid" or sub_status in _MAILBOX_ABSENT:
        return "invalid"
    return _STATUS_MAP.get(raw_status, "unknown")


class ZeroBounceValidator:
    name = "zerobounce"

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=_TIMEOUT_SECONDS)

    def validate(self, email: str) -> ValidationResult:
        if not is_valid_syntax(email):
            return ValidationResult.invalid("Not a valid email address.")

        try:
            response = self._client.get(
                ZEROBOUNCE_VALIDATE_URL,
                params={"api_key": self._api_key, "email": email, "ip_address": ""},
            )
        except httpx.HTTPError as exc:
            return ValidationResult.unknown(f"ZeroBounce request failed: {exc}.")

        if response.status_code >= 400:
            return ValidationResult.unknown(
                f"ZeroBounce returned HTTP {response.status_code}."
            )

        try:
            payload = response.json()
        except ValueError:
            return ValidationResult.unknown("ZeroBounce returned an unreadable response.")

        if error := payload.get("error"):
            return ValidationResult.unknown(f"ZeroBounce error: {error}.")

        raw_status = str(payload.get("status") or "unknown").lower()
        sub_status = str(payload.get("sub_status") or "").lower()

        status = verdict(raw_status, sub_status)
        detail = f"ZeroBounce: {raw_status}"
        if sub_status:
            detail += f" / {sub_status}"
        return ValidationResult(status, detail + ".")  # type: ignore[arg-type]
