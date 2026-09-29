"""Test doubles. No test in this suite touches the network."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from app.gmail.client import GmailProfile, GmailSendAs
from app.gmail.exceptions import GmailAmbiguousError, GmailPermanentError
from app.validation.base import DomainNotFoundError, ValidationResult


@dataclass
class FrozenClock:
    """A Clock that does not move unless told to."""

    fixed: dt.datetime

    def __post_init__(self) -> None:
        assert self.fixed.tzinfo is not None, "FrozenClock needs an aware datetime"

    def now(self) -> dt.datetime:
        return self.fixed

    def advance(self, **kwargs: float) -> None:
        self.fixed += dt.timedelta(**kwargs)


@dataclass
class FakeValidator:
    """Returns a canned verdict, per-address or a default."""

    name: str = "fake"
    default: ValidationResult = field(
        default_factory=lambda: ValidationResult.valid("fake validator")
    )
    by_email: dict[str, ValidationResult] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def validate(self, email: str) -> ValidationResult:
        self.calls.append(email)
        return self.by_email.get(email, self.default)


@dataclass
class FakeMxResolver:
    """MxResolver backed by dicts, so MX behaviour is testable without DNS."""

    mx: dict[str, list[str]] = field(default_factory=dict)
    addresses: set[str] = field(default_factory=set)
    nxdomain: set[str] = field(default_factory=set)

    def mx_hosts(self, domain: str) -> list[str]:
        if domain in self.nxdomain:
            raise DomainNotFoundError(domain)
        return self.mx.get(domain, [])

    def has_address_record(self, domain: str) -> bool:
        if domain in self.nxdomain:
            raise DomainNotFoundError(domain)
        return domain in self.addresses


@dataclass
class FakeGmailClient:
    """Records what would have been sent."""

    email_address: str = "joey@kinnatic.ai"
    display_name: str = "Joey"
    signature_html: str = (
        '<div dir="ltr"><b>Joey</b><br>CEO, Kinnatic Pty Ltd<br>'
        '<a href="https://kinnatic.ai">kinnatic.ai</a></div>'
    )
    sent_raw: list[str] = field(default_factory=list)
    next_message_id: str = "gmail-msg-1"
    fail_permanent: bool = False
    fail_ambiguous: bool = False
    # query -> message ids, and id -> full message payload
    listings: dict[str, list[str]] = field(default_factory=dict)
    messages: dict[str, dict] = field(default_factory=dict)
    rfc822_hits: dict[str, str] = field(default_factory=dict)

    def get_profile(self) -> GmailProfile:
        return GmailProfile(email_address=self.email_address, messages_total=len(self.sent_raw))

    def get_send_as(self, email: str) -> GmailSendAs:
        return GmailSendAs(
            email_address=email or self.email_address,
            display_name=self.display_name,
            signature=self.signature_html,
            is_primary=True,
            is_default=True,
        )

    def send(self, raw: str) -> str:
        if self.fail_permanent:
            raise GmailPermanentError("HTTP 400: fake permanent failure")
        if self.fail_ambiguous:
            raise GmailAmbiguousError("HTTP 503: fake ambiguous failure")
        self.sent_raw.append(raw)
        return self.next_message_id

    def list_message_ids(self, query: str, max_results: int = 100) -> list[str]:
        if query.startswith("rfc822msgid:"):
            key = query.removeprefix("rfc822msgid:")
            hit = self.rfc822_hits.get(key)
            return [hit] if hit else []
        return self.listings.get(query, [])[:max_results]

    def get_message(self, message_id: str) -> dict:
        return self.messages.get(message_id, {"payload": {}})

    def find_by_rfc822_id(self, rfc822_message_id: str) -> str | None:
        return self.rfc822_hits.get(rfc822_message_id.strip("<>"))

    # --- helpers for building inbox-sync fixtures -------------------------------
    def stage_inbox(self, query: str, messages: dict[str, dict]) -> None:
        self.listings[query] = list(messages)
        self.messages.update(messages)
