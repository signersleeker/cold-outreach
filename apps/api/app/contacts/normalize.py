"""Email and name normalisation. Pure — no I/O."""

from __future__ import annotations

import re

from app.contacts.constants import CONSUMER_DOMAINS

# Pragmatic address shape. Not a full RFC 5322 grammar (which permits quoted
# strings and comments no real prospect list contains) — it rejects what would
# fail at a mail server and accepts what would not.
EMAIL_RE = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$"
)

MAX_EMAIL_LENGTH = 320


def normalize_email(raw: str) -> str:
    """Trim, unwrap, and lowercase an address.

    Lowercasing the local part is not RFC-strict (local parts are formally
    case-sensitive) but it is correct for Gmail and Google Workspace and it is
    what makes the case-insensitive duplicate check work.
    """
    value = (raw or "").strip()
    if not value:
        return ""
    # "Avery Stone <avery@x.com>" -> "avery@x.com"
    if "<" in value and ">" in value:
        start = value.rindex("<") + 1
        end = value.rindex(">")
        if start < end:
            value = value[start:end].strip()
    value = value.strip("\"'").replace(" ", "")
    if value.lower().startswith("mailto:"):
        value = value[len("mailto:") :]
    return value.lower()


def is_valid_syntax(email: str) -> bool:
    return bool(email) and len(email) <= MAX_EMAIL_LENGTH and bool(EMAIL_RE.match(email))


def domain_of(email: str) -> str:
    _, _, domain = email.rpartition("@")
    return domain.lower()


def is_consumer_domain(email: str) -> bool:
    return domain_of(email) in CONSUMER_DOMAINS


def split_full_name(full_name: str) -> tuple[str, str]:
    """Best-effort first/last split, used only when no first/last columns exist."""
    parts = (full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])
