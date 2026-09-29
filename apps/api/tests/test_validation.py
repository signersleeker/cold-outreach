"""Email validation. Pure — DNS and HTTP are both injected."""

from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.contacts.normalize import is_valid_syntax
from app.validation.factory import build_validator
from app.validation.mx import NULL_MX, SyntaxMxValidator
from app.validation.zerobounce import ZEROBOUNCE_VALIDATE_URL, ZeroBounceValidator
from tests.fakes import FakeMxResolver


def mx_validator(**kwargs) -> SyntaxMxValidator:
    return SyntaxMxValidator(FakeMxResolver(**kwargs))


# ------------------------------------------------------------------- syntax ----
@pytest.mark.parametrize(
    "email",
    [
        "avery@northwind.example",
        "avery.stone@northwind.example",
        "avery+tag@northwind.example",
        "a@b.co",
        "avery_stone@sub.northwind.example",
    ],
)
def test_valid_syntax_accepted(email: str) -> None:
    assert is_valid_syntax(email) is True


@pytest.mark.parametrize(
    "email",
    [
        "",
        "avery",
        "avery@",
        "@northwind.example",
        "avery@northwind",
        "avery @northwind.example",
        "avery@@northwind.example",
        "avery@.example",
        "a" * 321 + "@x.com",
    ],
)
def test_invalid_syntax_rejected(email: str) -> None:
    assert is_valid_syntax(email) is False


def test_bad_syntax_is_invalid_without_any_dns_lookup() -> None:
    resolver = FakeMxResolver()
    assert SyntaxMxValidator(resolver).validate("not-an-email").status == "invalid"


# ---------------------------------------------------------------------- MX ----
def test_domain_with_mx_is_valid() -> None:
    validator = mx_validator(mx={"northwind.example": ["mx1.northwind.example"]})
    result = validator.validate("avery@northwind.example")
    assert result.status == "valid"
    assert "MX record" in result.detail


def test_mx_verdict_is_identical_for_a_real_and_a_nonexistent_mailbox() -> None:
    """The crux: DNS cannot tell mailboxes apart.

    A "valid" verdict from this validator means the domain accepts mail. A
    nonexistent address on a deliverable domain is indistinguishable from a real
    one, and only a bounce (or ZeroBounce) reveals the difference.
    """
    validator = mx_validator(mx={"kinnatic.ai": ["aspmx.l.google.com"]})
    real = validator.validate("joey@kinnatic.ai")
    fake = validator.validate("ben@kinnatic.ai")

    assert real.status == fake.status == "valid"
    assert real.detail == fake.detail


def test_valid_detail_discloses_that_only_the_domain_was_checked() -> None:
    """The detail string is what the operator reads, so it must not overclaim."""
    validator = mx_validator(mx={"kinnatic.ai": ["aspmx.l.google.com"]})
    detail = validator.validate("ben@kinnatic.ai").detail.lower()

    assert "mailbox not" in detail or "not verified" in detail
    assert "zerobounce" in detail, "points at the way to actually verify a mailbox"


def test_null_mx_is_invalid() -> None:
    """RFC 7505: a single MX of "." declares the domain accepts no mail.

    example.com publishes exactly this, so a naive "any MX records?" check would
    wrongly report it deliverable.
    """
    validator = mx_validator(mx={"example.com": [NULL_MX]})
    result = validator.validate("dana@example.com")
    assert result.status == "invalid"
    assert "null MX" in result.detail


def test_nxdomain_is_invalid() -> None:
    validator = mx_validator(nxdomain={"no-such-domain.test"})
    result = validator.validate("e.laurent@no-such-domain.test")
    assert result.status == "invalid"
    assert "does not exist" in result.detail


def test_no_mx_but_an_a_record_is_risky_not_valid() -> None:
    """RFC 5321 allows the A-record fallback, but a web-only domain rarely takes mail."""
    validator = mx_validator(addresses={"weblonly.example"})
    result = validator.validate("avery@weblonly.example")
    assert result.status == "risky"
    assert "no MX record" in result.detail


def test_no_mx_and_no_a_record_is_invalid() -> None:
    result = mx_validator().validate("avery@nothing.example")
    assert result.status == "invalid"


def test_disposable_domain_is_invalid_before_any_lookup() -> None:
    validator = mx_validator(mx={"mailinator.com": ["mx.mailinator.com"]})
    result = validator.validate("throwaway@mailinator.com")
    assert result.status == "invalid"
    assert "disposable" in result.detail


def test_dns_failure_is_unknown_not_invalid() -> None:
    """An outage must not permanently suppress a perfectly good address."""
    import dns.exception

    class Flaky:
        def mx_hosts(self, domain: str) -> list[str]:
            raise dns.exception.Timeout()

        def has_address_record(self, domain: str) -> bool:
            raise dns.exception.Timeout()

    result = SyntaxMxValidator(Flaky()).validate("avery@northwind.example")
    assert result.status == "unknown"


def test_mixed_null_and_real_mx_is_valid() -> None:
    validator = mx_validator(mx={"mixed.example": [NULL_MX, "mx1.mixed.example"]})
    assert validator.validate("avery@mixed.example").status == "valid"


# --------------------------------------------------------------- ZeroBounce ----
def zb(payload: dict, status_code: int = 200) -> ZeroBounceValidator:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(ZEROBOUNCE_VALIDATE_URL)
        return httpx.Response(status_code, json=payload)

    transport = httpx.MockTransport(handler)
    return ZeroBounceValidator("test-key", httpx.Client(transport=transport))


@pytest.mark.parametrize(
    ("zb_status", "expected"),
    [
        ("valid", "valid"),
        ("invalid", "invalid"),
        ("catch-all", "risky"),
        ("spamtrap", "invalid"),
        ("abuse", "invalid"),
        ("do_not_mail", "invalid"),
        ("unknown", "unknown"),
        ("something-new", "unknown"),
    ],
)
def test_zerobounce_status_mapping(zb_status: str, expected: str) -> None:
    result = zb({"status": zb_status, "sub_status": ""}).validate("avery@northwind.example")
    assert result.status == expected


def test_zerobounce_disposable_sub_status_overrides_a_valid_status() -> None:
    result = zb({"status": "valid", "sub_status": "disposable"}).validate("a@mailinator.com")
    assert result.status == "invalid"


def test_role_inbox_exists_so_it_is_valid() -> None:
    """info@ / admin@ / reception@ come back do_not_mail / role_based.

    ZeroBounce documents those as real mailboxes. The do_not_mail label is a
    bulk-sender warning, not "this address does not exist".
    """
    result = zb({"status": "do_not_mail", "sub_status": "role_based"}).validate(
        "reception@clinic.example"
    )
    assert result.status == "valid"
    assert "role_based" in result.detail


def test_mailbox_not_found_is_invalid() -> None:
    result = zb({"status": "invalid", "sub_status": "mailbox_not_found"}).validate(
        "nobody@clinic.example"
    )
    assert result.status == "invalid"


@pytest.mark.parametrize(
    "sub_status",
    ["no_dns_entries", "does_not_accept_mail"],
)
def test_undeliverable_domain_is_invalid(sub_status: str) -> None:
    result = zb({"status": "invalid", "sub_status": sub_status}).validate("a@missing.example")
    assert result.status == "invalid"


def test_role_inbox_on_a_catch_all_domain_is_not_confirmed() -> None:
    result = zb({"status": "do_not_mail", "sub_status": "role_based_catch_all"}).validate(
        "info@catchall.example"
    )
    assert result.status == "risky"


def test_zerobounce_error_field_yields_unknown() -> None:
    result = zb({"error": "Invalid API key"}).validate("avery@northwind.example")
    assert result.status == "unknown"
    assert "Invalid API key" in result.detail


def test_zerobounce_http_error_yields_unknown() -> None:
    result = zb({}, status_code=500).validate("avery@northwind.example")
    assert result.status == "unknown"


def test_zerobounce_transport_failure_yields_unknown() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    validator = ZeroBounceValidator("k", httpx.Client(transport=httpx.MockTransport(boom)))
    assert validator.validate("avery@northwind.example").status == "unknown"


def test_zerobounce_rejects_bad_syntax_without_calling_the_api() -> None:
    def must_not_be_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the API must not be called for malformed input")

    validator = ZeroBounceValidator(
        "k", httpx.Client(transport=httpx.MockTransport(must_not_be_called))
    )
    assert validator.validate("nonsense").status == "invalid"


def test_zerobounce_detail_names_the_provider() -> None:
    result = zb({"status": "catch-all", "sub_status": ""}).validate("a@catchall.example")
    assert "ZeroBounce" in result.detail


# ------------------------------------------------------------------ factory ----
def test_factory_uses_mx_when_no_api_key_is_set() -> None:
    settings = Settings(database_url="postgres://x/y", zerobounce_api_key="")
    assert build_validator(settings).name == "syntax+mx"


def test_factory_uses_zerobounce_when_a_key_is_set() -> None:
    settings = Settings(database_url="postgres://x/y", zerobounce_api_key="abc123")
    assert build_validator(settings).name == "zerobounce"


def test_factory_treats_whitespace_only_key_as_absent() -> None:
    settings = Settings(database_url="postgres://x/y", zerobounce_api_key="   ")
    assert build_validator(settings).name == "syntax+mx"
