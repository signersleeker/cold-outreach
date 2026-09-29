"""Syntax + MX validation. The default path when no ZeroBounce key is set.

**This checks the domain, not the mailbox.** DNS carries no per-mailbox
information, so a "valid" verdict here means "this domain accepts mail", not
"this person exists". `ben@example.com` and `joey@example.com` are
indistinguishable to every check in this module.

Confirming an individual mailbox needs either an SMTP probe — which this app
never does, because it gets the sending IP blocklisted and is unreliable against
catch-all and greylisting domains — or a commercial validator. Set
ZEROBOUNCE_API_KEY for the latter.

Detail strings below say so explicitly, because they are what the operator reads
on the contact page.
"""

from __future__ import annotations

import dns.exception
import dns.resolver

from app.contacts.normalize import domain_of, is_valid_syntax
from app.validation.base import (
    DomainNotFoundError,
    MxResolver,
    ValidationResult,
)
from app.validation.disposable import is_disposable

# RFC 7505: a single MX whose exchange is "." is an explicit declaration that the
# domain accepts no mail. example.com publishes exactly this, so a naive "did the
# lookup return any records?" check would wrongly call it deliverable.
NULL_MX = "."

_DNS_TIMEOUT_SECONDS = 5.0


class DnsPythonResolver:
    """MxResolver backed by dnspython."""

    def __init__(self, timeout: float = _DNS_TIMEOUT_SECONDS) -> None:
        self._resolver = dns.resolver.Resolver()
        self._resolver.timeout = timeout
        self._resolver.lifetime = timeout

    def mx_hosts(self, domain: str) -> list[str]:
        try:
            answers = self._resolver.resolve(domain, "MX")
        except dns.resolver.NXDOMAIN as exc:
            raise DomainNotFoundError(domain) from exc
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            return []
        return [str(record.exchange).rstrip(".") or NULL_MX for record in answers]

    def has_address_record(self, domain: str) -> bool:
        for record_type in ("A", "AAAA"):
            try:
                if self._resolver.resolve(domain, record_type):
                    return True
            except dns.resolver.NXDOMAIN as exc:
                raise DomainNotFoundError(domain) from exc
            except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
                continue
            except dns.exception.DNSException:
                return False
        return False


class SyntaxMxValidator:
    name = "syntax+mx"

    def __init__(self, resolver: MxResolver) -> None:
        self._resolver = resolver

    def validate(self, email: str) -> ValidationResult:
        if not is_valid_syntax(email):
            return ValidationResult.invalid("Not a valid email address.")

        domain = domain_of(email)
        if is_disposable(domain):
            return ValidationResult.invalid(f"{domain} is a disposable mailbox provider.")

        try:
            hosts = self._resolver.mx_hosts(domain)
        except DomainNotFoundError:
            return ValidationResult.invalid(f"Domain {domain} does not exist.")
        except dns.exception.DNSException as exc:
            return ValidationResult.unknown(f"DNS lookup for {domain} failed: {exc}.")

        if hosts:
            if all(host == NULL_MX for host in hosts):
                return ValidationResult.invalid(
                    f"{domain} publishes a null MX record: it accepts no email."
                )
            return ValidationResult.valid(
                f"{domain} accepts mail ({len(hosts)} MX records). Domain checked, "
                "mailbox not — DNS cannot confirm a specific address exists. "
                "Set ZEROBOUNCE_API_KEY to verify mailboxes."
            )

        # No MX. RFC 5321 says fall back to the A record, but in practice a domain
        # with web hosting and no MX is usually not a mail domain at all, so this
        # is reported as risky rather than valid.
        try:
            if self._resolver.has_address_record(domain):
                return ValidationResult.risky(
                    f"{domain} has no MX record; mail would fall back to its A record."
                )
        except DomainNotFoundError:
            return ValidationResult.invalid(f"Domain {domain} does not exist.")
        except dns.exception.DNSException as exc:
            return ValidationResult.unknown(f"DNS lookup for {domain} failed: {exc}.")

        return ValidationResult.invalid(f"{domain} has no MX or address record.")
