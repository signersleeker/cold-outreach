"""Final body assembly: opt-out sentence + unsubscribe line. Pure — no I/O.

Order for the gate body (no signature): rendered body -> opt-out (if missing)
-> blank line -> unsubscribe URL.

The HTML signature from Gmail is attached later in mime.py. It is deliberately
kept out of this module so the multiple_links warning never counts signature
links.
"""

from __future__ import annotations

from app.lib.text import comparable, non_empty_lines
from app.templates.constants import OPT_OUT_SENTENCE

_TAIL_LINES = 8


def has_opt_out(body: str) -> bool:
    """True when the body already ends with the human opt-out sentence.

    Compared case-, quote- and whitespace-insensitively so a curly apostrophe
    or a rewrapped line still matches.
    """
    tail = comparable("\n".join(non_empty_lines(body)[-_TAIL_LINES:]))
    if not tail:
        return False
    return comparable(OPT_OUT_SENTENCE) in tail


def ensure_opt_out(body: str) -> str:
    """Append the opt-out sentence unless one is already present. Idempotent."""
    if has_opt_out(body):
        return body
    if not body.strip():
        return OPT_OUT_SENTENCE
    return f"{body.rstrip()}\n\n{OPT_OUT_SENTENCE}"


def format_unsub_line(unsub_url: str) -> str:
    """Plain-text unsubscribe footer.

    Plain text cannot hide a URL behind a word, so the address stays visible
    for text-only clients. The HTML alternative uses link text "Unsubscribe".
    """
    return f"Unsubscribe: {unsub_url}"


def append_unsub_line(body: str, unsub_url: str) -> str:
    """Put the unsubscribe line on its own line. Idempotent."""
    if not unsub_url or unsub_url in body:
        return body
    return f"{body.rstrip()}\n\n{format_unsub_line(unsub_url)}"


def compose_gate_body(rendered_body: str, *, unsub_url: str) -> str:
    """Body used for gates and link counting — no Gmail signature."""
    return append_unsub_line(ensure_opt_out(rendered_body), unsub_url)


def compose_plain_body(
    rendered_body: str,
    *,
    signature_plain: str,
    unsub_url: str,
) -> str:
    """The exact plain-text body that will be sent and archived.

    Order: rendered body -> tag-stripped signature -> opt-out -> unsub URL.
    """
    parts = [rendered_body.rstrip()]
    sig = signature_plain.strip()
    if sig:
        parts.append(sig)
    body = "\n\n".join(p for p in parts if p)
    return append_unsub_line(ensure_opt_out(body), unsub_url)
