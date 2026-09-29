"""Small pure text helpers shared across slices."""

from __future__ import annotations

import re

_HTTP_LINK_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def count_http_links(text: str) -> int:
    """Number of http(s) URLs in a body.

    Used by the `multiple_links` warning. The unsubscribe line we append counts,
    which is deliberate: one link (the unsub URL) is normal, two means the
    template itself carries a link and the message starts to look like marketing.
    """
    return len(_HTTP_LINK_RE.findall(text))


def http_links(text: str) -> list[str]:
    return _HTTP_LINK_RE.findall(text)


def collapse_ws(text: str) -> str:
    """Whitespace-insensitive form, for comparing sentences that may be rewrapped."""
    return _WS_RE.sub(" ", text).strip()


def normalize_quotes(text: str) -> str:
    """Fold typographic quotes to ASCII.

    The opt-out sentence is stored with a straight apostrophe but an operator
    editing a template in a word processor may end up with a curly one. Without
    this, `has_identity_block` would miss it and append a second copy.
    """
    return (
        text.replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
    )


def comparable(text: str) -> str:
    """Case-, quote- and whitespace-insensitive form for presence checks."""
    return collapse_ws(normalize_quotes(text)).casefold()


def non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]
