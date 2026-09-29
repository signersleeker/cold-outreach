"""ZeroBounce validation, used when ZEROBOUNCE_API_KEY is set.

https://www.zerobounce.net/docs/email-validation-api-quickstart/
"""

from __future__ import annotations

import httpx

from app.contacts.normalize import is_valid_syntax
from app.validation.base import ValidationResult

ZEROBOUNCE_VALIDATE_URL = "https://api.zerobounce.net/v2/validate"

_TIMEOUT_SECONDS = 15.0

# ZeroBounce "status" -> our vocabulary.
#   catch-all  : the domain accepts everything, so the mailbox may not exist.
#   do_not_mail: role accounts, complainers, toxic addresses. Treated as invalid
#                because sending to them is what generates complaints.
_STATUS_MAP = {
    "valid": "valid",
    "invalid": "invalid",
    "catch-all": "risky",
    "spamtrap": "invalid",
    "abuse": "invalid",
    "do_not_mail": "invalid",
    "unknown": "unknown",
}


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

        # A disposable address can come back as "valid" with the detail only in
        # sub_status, so this is checked ahead of the status map.
        if sub_status in ("disposable", "toxic", "global_suppression"):
            return ValidationResult.invalid(f"ZeroBounce: {raw_status} / {sub_status}.")

        status = _STATUS_MAP.get(raw_status, "unknown")
        detail = f"ZeroBounce: {raw_status}"
        if sub_status:
            detail += f" / {sub_status}"
        return ValidationResult(status, detail + ".")  # type: ignore[arg-type]
