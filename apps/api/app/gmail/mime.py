"""Build the RFC 822 message Gmail will send. Pure — no I/O.

multipart/alternative: text/plain for clients that ignore HTML, and text/html
so the Gmail account signature (logos, links, formatting) renders the same way
it does when composing in Gmail. The pitch is plain text. A linked word is
stored as [label](https://...), written out as "label (url)" in the plain
part, and turned into an anchor in the HTML part. The signature is the only
raw HTML we pass through.

There are no bulk headers here, and there is a hard assertion plus a test
that keeps it that way. That assertion is the machine-checkable form of
"this is not a blast tool".
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import re
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid

from app.gmail.constants import FORBIDDEN_HEADERS
from app.sends.services.compose import format_unsub_line, has_opt_out
from app.templates.constants import OPT_OUT_SENTENCE

_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_BREAK_RE = re.compile(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>|</h[1-6]>")
# Keep in sync with PLAIN_LINK in apps/web/src/lib/html-paste.ts.
_PLAIN_LINK_RE = re.compile(r"\[([^\[\]\n]+)\]\((https?://[^\s<>\"')\]]+)\)")


class ForbiddenHeaderError(RuntimeError):
    """A bulk-mail header was about to be written. Refuse to send."""


def new_message_id(from_email: str) -> str:
    """A Message-ID we generate ourselves, before the send.

    Persisted on the send_event so an interrupted send can be reconciled later
    with a Gmail `rfc822msgid:` search.
    """
    _, _, domain = from_email.rpartition("@")
    return make_msgid(domain=domain or None)


def html_to_plain(fragment: str) -> str:
    """Best-effort plain text from a Gmail HTML signature."""
    if not fragment:
        return ""
    text = _BLOCK_BREAK_RE.sub("\n", fragment)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    lines = [line.rstrip() for line in text.splitlines()]
    out: list[str] = []
    blank = False
    for line in lines:
        if line.strip():
            out.append(line.strip())
            blank = False
        elif out and not blank:
            out.append("")
            blank = True
    return "\n".join(out).strip()


def link_markup_to_plain(text: str) -> str:
    """Turn [label](url) into 'label (url)' for the text/plain part.

    Plain text cannot hide a URL behind a word. The HTML alternative keeps
    the word as the link.
    """
    return _PLAIN_LINK_RE.sub(lambda match: f"{match.group(1)} ({match.group(2)})", text)


def plain_to_html(text: str) -> str:
    """Escape a plain-text body for the HTML alternative.

    [label](https://...) becomes an anchor. Every other character is escaped,
    so a template cannot inject markup.
    """
    parts: list[str] = []
    last = 0
    for match in _PLAIN_LINK_RE.finditer(text):
        parts.append(_escape_with_breaks(text[last : match.start()]))
        href = html.escape(match.group(2), quote=True)
        label = html.escape(match.group(1))
        parts.append(f'<a href="{href}">{label}</a>')
        last = match.end()
    parts.append(_escape_with_breaks(text[last:]))
    return "".join(parts)


def _escape_with_breaks(text: str) -> str:
    return html.escape(text).replace("\n", "<br>\n")


def build_message_parts(
    *,
    rendered_body: str,
    signature_html: str,
    unsub_url: str,
) -> tuple[str, str]:
    """Return (plain_body, html_body) with consistent ordering.

    Order: rendered body -> signature -> opt-out -> unsub URL.
    An extra blank line separates the pitch from the signature so it reads
    like a Gmail-composed message.
    """
    pitch_source = rendered_body.rstrip()
    pitch = link_markup_to_plain(pitch_source)
    needs_opt_out = not has_opt_out(pitch)
    plain_sig = html_to_plain(signature_html)

    if pitch and plain_sig:
        body_plain = f"{pitch}\n\n\n{plain_sig}"
    elif pitch:
        body_plain = pitch
    else:
        body_plain = plain_sig

    if needs_opt_out:
        body_plain = (
            f"{body_plain.rstrip()}\n\n{OPT_OUT_SENTENCE}" if body_plain else OPT_OUT_SENTENCE
        )
    if unsub_url and unsub_url not in body_plain:
        body_plain = f"{body_plain.rstrip()}\n\n{format_unsub_line(unsub_url)}"

    html_chunks: list[str] = []
    if pitch_source:
        html_chunks.append(f"<div>{plain_to_html(pitch_source)}</div>")
    if signature_html.strip():
        # Two breaks = one blank visual line between pitch and signature.
        html_chunks.append("<div><br></div>")
        html_chunks.append(signature_html.strip())
    if needs_opt_out:
        html_chunks.append(f"<div>{plain_to_html(OPT_OUT_SENTENCE)}</div>")
    if unsub_url:
        escaped = html.escape(unsub_url)
        html_chunks.append(f'<div><a href="{escaped}">Unsubscribe</a></div>')
    return body_plain, "\n".join(html_chunks)


def build_outbound_message(
    *,
    to_email: str,
    to_name: str,
    from_email: str,
    sender_name: str,
    reply_to: str,
    subject: str,
    body_plain: str,
    body_html: str,
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

    msg.set_content(body_plain, subtype="plain", charset="utf-8")
    msg.add_alternative(body_html, subtype="html", charset="utf-8")

    present = {key.lower() for key in msg}
    offending = sorted(FORBIDDEN_HEADERS & present)
    if offending:
        raise ForbiddenHeaderError(f"refusing to send with bulk headers: {', '.join(offending)}")
    return msg


def encode_raw(msg: EmailMessage) -> str:
    """base64url of the full message, as Gmail's `raw` field expects."""
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
