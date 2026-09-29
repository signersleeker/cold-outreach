"""Email validation contract.

Two implementations: ZeroBounce when an API key is configured, otherwise a
syntax + MX check via dnspython. Neither ever opens an SMTP connection to a
prospect's mail server — that is what gets a sending IP blocklisted, and
tests/validation/test_no_smtp_probe.py enforces it by scanning this package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from app.contacts.constants import (
    VALIDATION_INVALID,
    VALIDATION_RISKY,
    VALIDATION_UNKNOWN,
    VALIDATION_VALID,
)

ValidationStatus = Literal["valid", "invalid", "risky", "unknown"]


@dataclass(frozen=True)
class ValidationResult:
    status: ValidationStatus
    detail: str
    # A transport failure is not durable: the contact can show `unknown`, but
    # nothing is written to email_validations, so a later import tries again.
    durable: bool = True
    provider_status: str = ""
    provider_sub_status: str = ""
    provider_payload: dict | None = None

    @classmethod
    def valid(cls, detail: str) -> ValidationResult:
        return cls(VALIDATION_VALID, detail)

    @classmethod
    def invalid(cls, detail: str) -> ValidationResult:
        return cls(VALIDATION_INVALID, detail)

    @classmethod
    def risky(cls, detail: str) -> ValidationResult:
        return cls(VALIDATION_RISKY, detail)

    @classmethod
    def unknown(cls, detail: str, *, durable: bool = True) -> ValidationResult:
        return cls(VALIDATION_UNKNOWN, detail, durable=durable)


class EmailValidator(Protocol):
    name: str

    def validate(self, email: str) -> ValidationResult: ...


class MxResolver(Protocol):
    """Injected so MX behaviour can be unit-tested without touching DNS."""

    def mx_hosts(self, domain: str) -> list[str]:
        """MX exchanges for a domain. Empty list when the domain has none."""
        ...

    def has_address_record(self, domain: str) -> bool:
        """True when the domain has an A or AAAA record."""
        ...


class DomainNotFoundError(Exception):
    """The domain itself does not exist (NXDOMAIN)."""
