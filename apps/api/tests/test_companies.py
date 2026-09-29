"""Company model: find-or-create, import sharing, list API."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.companies import service as companies_service
from app.companies.company import Company
from app.contacts import service as contacts_service


def test_find_or_create_is_case_insensitive(db: Session) -> None:
    first = companies_service.find_or_create(db, "Northwind Mutual")
    second = companies_service.find_or_create(db, "northwind mutual")
    assert first is not None and second is not None
    assert first.id == second.id
    assert first.name == "Northwind Mutual"
    assert db.scalar(select(func.count()).select_from(Company)) == 1


def test_blank_name_yields_no_company(db: Session) -> None:
    assert companies_service.find_or_create(db, "  ") is None
    assert companies_service.find_or_create(db, "") is None


def test_create_company_rejects_blank_and_duplicate(db: Session) -> None:
    import pytest

    from app.lib.errors import AppError

    with pytest.raises(AppError) as blank:
        companies_service.create(db, "  ")
    assert blank.value.status_code == 400

    created = companies_service.create(db, "Northwind Mutual")
    assert created.name == "Northwind Mutual"

    with pytest.raises(AppError) as dup:
        companies_service.create(db, "northwind mutual")
    assert dup.value.status_code == 409


def test_import_shares_company_rows(db: Session, validator, clock) -> None:
    csv = (
        "Email,Company\n"
        "a@northwind.example,Northwind\n"
        "b@northwind.example,northwind\n"
        "c@solo.example,\n"
    )
    summary = contacts_service.import_csv(db, csv.encode(), validator=validator, clock=clock)
    assert summary.created == 3
    assert summary.skipped_existing_company == 0
    assert db.scalar(select(func.count()).select_from(Company)) == 1

    a = contacts_service.by_email(db, "a@northwind.example")
    b = contacts_service.by_email(db, "b@northwind.example")
    c = contacts_service.by_email(db, "c@solo.example")
    assert a is not None and b is not None and c is not None
    assert a.company_id == b.company_id
    assert a.company == "Northwind"
    assert c.company_id is None
    assert c.company == ""


def test_import_skips_rows_for_existing_companies(db: Session, validator, clock) -> None:
    companies_service.create(db, "Northwind")
    csv = (
        "Email,Company\n"
        "new@northwind.example,Northwind\n"
        "fresh@acme.example,Acme\n"
        "solo@example.com,\n"
    )
    summary = contacts_service.import_csv(db, csv.encode(), validator=validator, clock=clock)
    assert summary.skipped_existing_company == 1
    assert summary.created == 2
    assert contacts_service.by_email(db, "new@northwind.example") is None
    assert contacts_service.by_email(db, "fresh@acme.example") is not None
    assert contacts_service.by_email(db, "solo@example.com") is not None


def test_make_contact_without_company(db: Session, make_contact) -> None:
    contact = make_contact(email="solo@example.com", company="")
    assert contact.company_id is None
    assert contact.company == ""


def test_search_companies_and_filter_contacts(db: Session, make_contact) -> None:
    make_contact(email="a@northwind.example", company="Northwind Mutual")
    make_contact(email="b@acme.example", company="Acme")
    make_contact(email="c@solo.example", company="")

    rows, total = companies_service.search(db, q="north")
    assert total == 1
    assert rows[0][0].name == "Northwind Mutual"
    assert rows[0][1] == 1

    company_id = rows[0][0].id
    contacts, contact_total = contacts_service.search(db, company_id=company_id)
    assert contact_total == 1
    assert contacts[0].email == "a@northwind.example"


def test_update_company_name_reassigns(db: Session, make_contact) -> None:
    contact = make_contact(email="a@example.com", company="Northwind")
    first_id = contact.company_id
    updated = contacts_service.update(db, contact.id, {"company": "Acme"})
    assert updated.company == "Acme"
    assert updated.company_id != first_id
    cleared = contacts_service.update(db, contact.id, {"company": ""})
    assert cleared.company_id is None
    assert cleared.company == ""
