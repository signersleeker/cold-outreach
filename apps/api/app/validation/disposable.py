"""Known disposable / throwaway mailbox domains.

A bundled list goes stale — it is a floor, not a guarantee. ZeroBounce covers
this properly when configured; this exists so the free path catches the obvious
cases.
"""

from __future__ import annotations

DISPOSABLE_DOMAINS = frozenset(
    {
        "10minutemail.com",
        "20minutemail.com",
        "33mail.com",
        "anonaddy.com",
        "burnermail.io",
        "dispostable.com",
        "emailondeck.com",
        "fakeinbox.com",
        "getairmail.com",
        "getnada.com",
        "guerrillamail.com",
        "guerrillamail.info",
        "harakirimail.com",
        "inboxbear.com",
        "mailcatch.com",
        "maildrop.cc",
        "mailinator.com",
        "mailnesia.com",
        "mintemail.com",
        "mohmal.com",
        "moakt.com",
        "mytemp.email",
        "sharklasers.com",
        "spam4.me",
        "spamgourmet.com",
        "temp-mail.org",
        "tempinbox.com",
        "tempmail.net",
        "tempmailaddress.com",
        "throwawaymail.com",
        "trashmail.com",
        "yopmail.com",
        "yopmail.fr",
    }
)


def is_disposable(domain: str) -> bool:
    return domain.lower() in DISPOSABLE_DOMAINS
