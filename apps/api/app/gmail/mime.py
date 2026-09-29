"""Build the RFC 822 message Gmail will send. Pure — no I/O.

text/plain only. `EmailMessage.set_content` with no attachments and no
alternative part produces a single-part text/plain message, and handles RFC 2047
encoding of non-ASCII names and subjects for us.

There are no bulk headers here, and there is a hard assertion plus a test
(tests/sends/test_mime_plaintext_only.py) that keeps it that way. That assertion
is the machine-checkable form of "this is not a blast tool".
"""

from __future__ import annotations

import base64
import datetime as dt
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid

from app.gmail.constants import FORBIDDEN_HEADERS


class ForbiddenHeaderError(RuntimeError):
    """A bulk-mail header was about to be written. Refuse to send."""


def new_message_id(from_email: str) -> str:
    """A Message-ID we generate ourselves, before the send.

    Persisted on the send_event so an interrupted send can be reconciled later
    with a Gmail `rfc822msgid:` search.
    """
    _, _, domain = from_email.rpartition("@")
    return make_msgid(domain=domain or None)


def build_plain_text_message(
    *,
    to_email: str,
    to_name: str,
    from_email: str,
    sender_name: str,
    reply_to: str,
    subject: str,
    body: str,
    rfc822_message_id: str,
    now: dt.datetime,
) -> EmailMessage:
    msg = EmailMessage()
    recipient = to_name.strip()
    sender = sender_name.strip()
    msg["To"] = formataddr((recipient, to_email)) if recipient else to_email
    msg["From"] = formataddr((sender, from_email)) if sender else from_email
    msg["Reply-To"] = formataddr((sender, reply_to)) if sender else reply_to
    msg["Subject"] = subject
    msg["Message-ID"] = rfc822_message_id
    msg["Date"] = format_datetime(now)
    msg.set_content(body, subtype="plain", charset="utf-8")

    present = {key.lower() for key in msg}
    offending = sorted(FORBIDDEN_HEADERS & present)
    if offending:
        raise ForbiddenHeaderError(f"refusing to send with bulk headers: {', '.join(offending)}")
    return msg


def encode_raw(msg: EmailMessage) -> str:
    """base64url of the full message, as Gmail's `raw` field expects."""
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
