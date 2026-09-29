"""Classify replies and bounces from Gmail messages. Pure — no I/O.

Two rules here carry real consequences, because a wrong call permanently removes
a legitimate prospect:

1. Quoted text is stripped BEFORE stop-word matching. Our own footer says
   reply "no", and a friendly reply that quotes the thread would otherwise
   suppress someone who never asked to be removed.
2. Only permanent failures (SMTP status 5.x.x) suppress. A 4.x.x deferral, an
   out-of-office, or a full mailbox is recorded and left alone.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from enum import Enum

STOP_RE = re.compile(
    r"\b("
    r"stop"
    r"|unsubscribe"
    r"|no thanks|no thank you"
    r"|not interested"
    r"|remove me|take me off"
    r"|do not (?:email|contact)|don't (?:email|contact)"
    r"|opt me out|opt out"
    r")\b",
    re.IGNORECASE,
)

# Where a quoted reply begins. Everything from the first match onwards is the
# previous message, not what this person wrote.
_QUOTE_MARKERS = (
    re.compile(r"^\s*On .{0,200}\bwrote:\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*_{5,}\s*$", re.MULTILINE),
    re.compile(r"^\s*From:\s.+$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*Sent from my \w+", re.IGNORECASE | re.MULTILINE),
)

_DELIVERY_STATUS_RE = re.compile(
    r"^\s*Status:\s*([245])\.(\d+)\.(\d+)", re.IGNORECASE | re.MULTILINE
)
_FINAL_RECIPIENT_RE = re.compile(
    r"^\s*(?:Final|Original)-Recipient:\s*(?:rfc822\s*;)?\s*([^\s<>]+@[^\s<>]+)",
    re.IGNORECASE | re.MULTILINE,
)
_ANGLE_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

_BOUNCE_SENDERS = ("mailer-daemon", "postmaster")
_BOUNCE_SUBJECTS = (
    "delivery status notification",
    "undelivered mail returned to sender",
    "undeliverable",
    "mail delivery failed",
    "delivery has failed",
    "returned mail",
    "failure notice",
)
_AUTO_REPLY_SUBJECTS = (
    "out of office",
    "auto-reply",
    "automatic reply",
    "autoreply",
    "on annual leave",
)


class Classification(Enum):
    REPLY_STOP = "reply_stop"
    BOUNCE_PERMANENT = "bounce_permanent"
    BOUNCE_SOFT = "bounce_soft"
    AUTO_REPLY = "auto_reply"
    REPLY_OTHER = "reply_other"


@dataclass(frozen=True)
class ParsedMessage:
    classification: Classification
    from_email: str
    subject: str
    affected_email: str
    detail: str


def headers_to_dict(payload: dict) -> dict[str, str]:
    return {
        (h.get("name") or "").lower(): (h.get("value") or "")
        for h in payload.get("headers") or []
    }


def _decode_part(body: dict) -> str:
    data = body.get("data")
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""


def extract_text(payload: dict) -> str:
    """Depth-first walk of a Gmail payload, collecting text/plain and status parts."""
    collected: list[str] = []

    def walk(part: dict) -> None:
        mime = (part.get("mimeType") or "").lower()
        if mime.startswith("multipart/"):
            for sub in part.get("parts") or []:
                walk(sub)
            return
        if mime in (
            "text/plain",
            "message/delivery-status",
            "text/rfc822-headers",
            "message/rfc822",
        ):
            collected.append(_decode_part(part.get("body") or {}))
        elif mime == "text/html" and not collected:
            # Only fall back to HTML when there is no plain part at all.
            collected.append(re.sub(r"<[^>]+>", " ", _decode_part(part.get("body") or {})))

    walk(payload)
    return "\n".join(chunk for chunk in collected if chunk)


def strip_quoted_reply(text: str) -> str:
    """Keep only what this person actually typed.

    Cuts at the earliest quote marker, then drops leading '>' quote lines.
    """
    cut = len(text)
    for marker in _QUOTE_MARKERS:
        match = marker.search(text)
        if match and match.start() < cut:
            cut = match.start()
    own = text[:cut]
    kept = [line for line in own.splitlines() if not line.lstrip().startswith(">")]
    return "\n".join(kept).strip()


def extract_email(value: str) -> str:
    match = _ANGLE_EMAIL_RE.search(value or "")
    return match.group(0).lower() if match else ""


def is_bounce(from_email: str, subject: str) -> bool:
    local = from_email.split("@", 1)[0].lower()
    if any(marker in local for marker in _BOUNCE_SENDERS):
        return True
    lowered = subject.lower()
    return any(marker in lowered for marker in _BOUNCE_SUBJECTS)


def delivery_status_class(text: str) -> int | None:
    """Leading digit of the SMTP status: 5 permanent, 4 transient, 2 success."""
    match = _DELIVERY_STATUS_RE.search(text)
    return int(match.group(1)) if match else None


def extract_bounce_recipient(headers: dict[str, str], text: str) -> str:
    """Which address actually failed."""
    failed = headers.get("x-failed-recipients", "")
    if failed:
        return extract_email(failed.split(",")[0])
    match = _FINAL_RECIPIENT_RE.search(text)
    if match:
        return match.group(1).lower()
    return ""


def classify_message(payload: dict) -> ParsedMessage:
    headers = headers_to_dict(payload)
    from_email = extract_email(headers.get("from", ""))
    subject = headers.get("subject", "")
    raw_text = extract_text(payload)

    if is_bounce(from_email, subject):
        status = delivery_status_class(raw_text)
        recipient = extract_bounce_recipient(headers, raw_text)
        if status == 5:
            return ParsedMessage(
                Classification.BOUNCE_PERMANENT,
                from_email,
                subject,
                recipient,
                "permanent delivery failure (5.x.x)",
            )
        return ParsedMessage(
            Classification.BOUNCE_SOFT,
            from_email,
            subject,
            recipient,
            f"transient or unclassified delivery report (status {status or 'unknown'})",
        )

    lowered_subject = subject.lower()
    if any(marker in lowered_subject for marker in _AUTO_REPLY_SUBJECTS):
        return ParsedMessage(
            Classification.AUTO_REPLY, from_email, subject, from_email, "automatic reply"
        )

    own_words = strip_quoted_reply(raw_text)
    # Match on the subject too, but only the part the sender wrote — a subject is
    # never quoted, so "Re: ... unsubscribe" is a genuine signal.
    match = STOP_RE.search(own_words) or STOP_RE.search(subject)
    if match:
        return ParsedMessage(
            Classification.REPLY_STOP,
            from_email,
            subject,
            from_email,
            f'matched "{match.group(0)}"',
        )

    return ParsedMessage(Classification.REPLY_OTHER, from_email, subject, from_email, "reply")
