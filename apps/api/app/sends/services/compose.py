"""Final body assembly: identity block + unsubscribe line. Pure — no I/O.

Order is: rendered body -> identity block (if not already there) -> blank line
-> unsubscribe URL on its own line.

Both append steps must be idempotent. The seeded first-touch template already
ends with the sender name, the company, and the opt-out sentence, so a naive
append would sign every email twice.
"""

from __future__ import annotations

from app.lib.text import comparable, non_empty_lines
from app.templates.constants import OPT_OUT_SENTENCE

# How far back to look for an existing identity block. The block itself is 4
# lines; a couple of spare lines absorbs an operator's extra sign-off line.
_TAIL_LINES = 8


def build_identity_block(sender_name: str, sender_title: str, company_legal: str) -> str:
    """The plain-text identity footer.

    This is sender identification as required of a commercial electronic
    message, plus a human opt-out sentence. It is deliberately NOT a marketing
    unsubscribe footer, and there is no List-Unsubscribe header to match it.
    """
    lines = [sender_name, sender_title, company_legal, OPT_OUT_SENTENCE]
    return "\n".join(line for line in lines if line)


def has_identity_block(body: str, company_legal: str) -> bool:
    """True when the body already ends with an identity block.

    Requires both the legal entity name and the opt-out sentence, compared
    case-, quote- and whitespace-insensitively so a curly apostrophe or a
    rewrapped line still matches.
    """
    tail = comparable("\n".join(non_empty_lines(body)[-_TAIL_LINES:]))
    if not tail:
        return False
    has_opt_out = comparable(OPT_OUT_SENTENCE) in tail
    has_entity = bool(company_legal) and comparable(company_legal) in tail
    return has_opt_out and has_entity


def ensure_identity_block(
    body: str, *, sender_name: str, sender_title: str, company_legal: str
) -> str:
    """Append the identity block unless one is already present. Idempotent."""
    if has_identity_block(body, company_legal):
        return body
    block = build_identity_block(sender_name, sender_title, company_legal)
    if not block:
        return body
    return f"{body.rstrip()}\n\n{block}"


def append_unsub_line(body: str, unsub_url: str) -> str:
    """Put the unsubscribe URL on its own line. Idempotent."""
    if not unsub_url or unsub_url in body:
        return body
    return f"{body.rstrip()}\n\n{unsub_url}"


def compose_final_body(
    rendered_body: str,
    *,
    sender_name: str,
    sender_title: str,
    company_legal: str,
    unsub_url: str,
) -> str:
    """The exact body that will be sent, and the one shown in the preview."""
    body = ensure_identity_block(
        rendered_body,
        sender_name=sender_name,
        sender_title=sender_title,
        company_legal=company_legal,
    )
    return append_unsub_line(body, unsub_url)
