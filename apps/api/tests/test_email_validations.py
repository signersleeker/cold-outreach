"""Validation verdicts outlive the contact they were first recorded on."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.contacts import service as contacts_service
from app.suppressions import service as suppressions_service
from app.validation.base import ValidationResult
from app.validation.email_validation import get as validation_for_email


def test_import_stores_a_verdict_by_email(db: Session, validator, clock) -> None:
    validator.by_email["avery@northwind.example"] = ValidationResult.valid("has MX")
    contacts_service.import_csv(
        db, b"Email\navery@northwind.example\n", validator=validator, clock=clock
    )

    stored = validation_for_email(db, "avery@northwind.example")
    assert stored is not None
    assert stored.status == "valid"
    assert stored.detail == "has MX"
    assert stored.validator == "fake"
    assert stored.validated_at == clock.now()


def test_reimport_after_delete_reuses_the_stored_verdict(db: Session, validator, clock) -> None:
    validator.by_email["avery@northwind.example"] = ValidationResult.valid("has MX")
    contacts_service.import_csv(
        db, b"Email\navery@northwind.example\n", validator=validator, clock=clock
    )
    contact = contacts_service.by_email(db, "avery@northwind.example")
    assert contact is not None
    contacts_service.delete(db, contact.id)

    validator.calls.clear()
    validator.by_email["avery@northwind.example"] = ValidationResult.invalid("must not run")
    summary = contacts_service.import_csv(
        db, b"Email\navery@northwind.example\n", validator=validator, clock=clock
    )

    assert validator.calls == []
    assert summary.valid == 1
    assert summary.invalid == 0
    again = contacts_service.by_email(db, "avery@northwind.example")
    assert again is not None
    assert again.validation_status == "valid"
    assert again.validation_detail == "has MX"


def test_reimport_of_a_stored_invalid_address_suppresses_again(
    db: Session, validator, clock
) -> None:
    validator.by_email["bad@nowhere.invalid"] = ValidationResult.invalid("no MX record")
    contacts_service.import_csv(
        db, b"Email\nbad@nowhere.invalid\n", validator=validator, clock=clock
    )
    contact = contacts_service.by_email(db, "bad@nowhere.invalid")
    assert contact is not None
    contacts_service.delete(db, contact.id)
    assert suppressions_service.unsuppress(db, "bad@nowhere.invalid") is True

    validator.calls.clear()
    summary = contacts_service.import_csv(
        db, b"Email\nbad@nowhere.invalid\n", validator=validator, clock=clock
    )

    assert validator.calls == []
    assert summary.invalid == 1
    again = contacts_service.by_email(db, "bad@nowhere.invalid")
    assert again is not None and again.suppressed is True
    assert suppressions_service.is_suppressed(db, "bad@nowhere.invalid") is not None


def test_skip_leaves_an_unseen_address_pending_and_unstored(
    db: Session, validator, clock
) -> None:
    summary = contacts_service.import_csv(
        db,
        b"Email\nnew@northwind.example\n",
        validator=validator,
        clock=clock,
        skip_validation=True,
    )
    assert validator.calls == []
    assert summary.pending == 1
    contact = contacts_service.by_email(db, "new@northwind.example")
    assert contact is not None and contact.validation_status == "pending"
    assert validation_for_email(db, "new@northwind.example") is None


def test_skip_still_reuses_a_stored_verdict(db: Session, validator, clock) -> None:
    validator.by_email["avery@northwind.example"] = ValidationResult.valid("has MX")
    contacts_service.import_csv(
        db, b"Email\navery@northwind.example\n", validator=validator, clock=clock
    )
    contact = contacts_service.by_email(db, "avery@northwind.example")
    assert contact is not None
    contacts_service.delete(db, contact.id)

    validator.calls.clear()
    summary = contacts_service.import_csv(
        db,
        b"Email\navery@northwind.example\n",
        validator=validator,
        clock=clock,
        skip_validation=True,
    )
    assert validator.calls == []
    assert summary.valid == 1
    again = contacts_service.by_email(db, "avery@northwind.example")
    assert again is not None and again.validation_status == "valid"


def test_revalidate_overwrites_the_stored_verdict(db: Session, validator, clock) -> None:
    validator.by_email["avery@northwind.example"] = ValidationResult.valid("has MX")
    contacts_service.import_csv(
        db, b"Email\navery@northwind.example\n", validator=validator, clock=clock
    )
    contact = contacts_service.by_email(db, "avery@northwind.example")
    assert contact is not None

    validator.calls.clear()
    validator.by_email["avery@northwind.example"] = ValidationResult.risky("catch-all domain")
    updated = contacts_service.revalidate(db, contact.id, validator=validator, clock=clock)

    assert validator.calls == ["avery@northwind.example"]
    assert updated.validation_status == "risky"
    stored = validation_for_email(db, "avery@northwind.example")
    assert stored is not None
    assert stored.status == "risky"
    assert stored.detail == "catch-all domain"


def test_a_transport_failure_is_not_stored(db: Session, clock) -> None:
    class Flaky:
        name = "flaky"

        def validate(self, email: str) -> ValidationResult:
            return ValidationResult.unknown("DNS is down.", durable=False)

    summary = contacts_service.import_csv(
        db, b"Email\navery@northwind.example\n", validator=Flaky(), clock=clock
    )
    assert summary.pending == 1
    contact = contacts_service.by_email(db, "avery@northwind.example")
    assert contact is not None and contact.validation_status == "unknown"
    assert validation_for_email(db, "avery@northwind.example") is None


def test_zerobounce_payload_is_stored_with_the_verdict(db: Session, clock) -> None:
    payload = {"status": "valid", "sub_status": "role_based", "free_email": False}

    class ZeroBounce:
        name = "zerobounce"

        def validate(self, email: str) -> ValidationResult:
            return ValidationResult(
                "valid",
                "ZeroBounce: valid / role_based.",
                provider_status="valid",
                provider_sub_status="role_based",
                provider_payload=payload,
            )

    contacts_service.import_csv(
        db, b"Email\ninfo@clinic.example\n", validator=ZeroBounce(), clock=clock
    )
    stored = validation_for_email(db, "info@clinic.example")
    assert stored is not None
    assert stored.validator == "zerobounce"
    assert stored.provider_status == "valid"
    assert stored.provider_sub_status == "role_based"
    assert stored.provider_payload == payload


def test_create_reuses_a_stored_verdict(db: Session, validator, clock) -> None:
    validator.by_email["avery@northwind.example"] = ValidationResult.valid("has MX")
    contacts_service.import_csv(
        db, b"Email\navery@northwind.example\n", validator=validator, clock=clock
    )
    contact = contacts_service.by_email(db, "avery@northwind.example")
    assert contact is not None
    contacts_service.delete(db, contact.id)

    validator.calls.clear()
    validator.by_email["avery@northwind.example"] = ValidationResult.invalid("must not run")
    created = contacts_service.create(
        db, email="avery@northwind.example", validator=validator, clock=clock
    )
    assert validator.calls == []
    assert created.validation_status == "valid"
    assert created.validation_detail == "has MX"
