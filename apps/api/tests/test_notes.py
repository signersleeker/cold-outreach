"""Polymorphic notes: a contact and a company each keep their own."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contacts import service as contacts_service
from app.lib.errors import AppError
from app.notes import service as notes_service
from app.notes.constants import NOTABLE_COMPANY, NOTABLE_CONTACT
from app.notes.note import Note


def test_a_contact_and_its_company_keep_separate_notes(db: Session, contact) -> None:
    assert contact.company_id is not None
    contact_note = notes_service.create(
        db, notable_type=NOTABLE_CONTACT, notable_id=contact.id, body="  Called Tuesday  "
    )
    company_note = notes_service.create(
        db, notable_type=NOTABLE_COMPANY, notable_id=contact.company_id, body="APRA review open"
    )

    assert contact_note.body == "Called Tuesday"
    contact_notes = notes_service.list_for(db, NOTABLE_CONTACT, contact.id)
    company_notes = notes_service.list_for(db, NOTABLE_COMPANY, contact.company_id)
    assert [note.id for note in contact_notes] == [contact_note.id]
    assert [note.id for note in company_notes] == [company_note.id]


def test_blank_and_unknown_targets_are_rejected(db: Session, contact) -> None:
    with pytest.raises(AppError) as blank:
        notes_service.create(
            db, notable_type=NOTABLE_CONTACT, notable_id=contact.id, body="   "
        )
    assert blank.value.status_code == 400

    with pytest.raises(AppError) as missing:
        notes_service.create(
            db, notable_type=NOTABLE_CONTACT, notable_id=uuid.uuid4(), body="hello"
        )
    assert missing.value.status_code == 404

    with pytest.raises(AppError) as unknown:
        notes_service.create(
            db, notable_type="template", notable_id=contact.id, body="hello"
        )
    assert unknown.value.status_code == 400


def test_deleting_a_contact_removes_its_notes_only(db: Session, contact) -> None:
    company_id = contact.company_id
    assert company_id is not None
    notes_service.create(
        db, notable_type=NOTABLE_CONTACT, notable_id=contact.id, body="contact note"
    )
    company_note = notes_service.create(
        db, notable_type=NOTABLE_COMPANY, notable_id=company_id, body="company note"
    )

    contacts_service.delete(db, contact.id)

    assert notes_service.list_for(db, NOTABLE_COMPANY, company_id)[0].id == company_note.id
    assert (
        db.scalar(
            select(func.count()).select_from(Note).where(Note.notable_type == NOTABLE_CONTACT)
        )
        == 0
    )


def test_import_writes_contact_and_company_notes(db: Session, validator, clock) -> None:
    csv = (
        "Email,Company,Notes,Contact Notes,Company Notes\n"
        "a@northwind.example,Northwind,free text,Spoke at AusCERT,Shared vendor\n"
        "b@northwind.example,Northwind,,Followed up,Shared vendor\n"
        "c@solo.example,,,Solo note,Nowhere to put this\n"
    )
    summary = contacts_service.import_csv(db, csv.encode(), validator=validator, clock=clock)
    assert summary.created == 3

    avery = contacts_service.by_email(db, "a@northwind.example")
    bao = contacts_service.by_email(db, "b@northwind.example")
    solo = contacts_service.by_email(db, "c@solo.example")
    assert avery is not None and bao is not None and solo is not None
    assert avery.notes == ""
    assert avery.company_id == bao.company_id
    assert solo.company_id is None

    assert [note.body for note in notes_service.list_for(db, NOTABLE_CONTACT, avery.id)] == [
        "Spoke at AusCERT"
    ]
    assert [note.body for note in notes_service.list_for(db, NOTABLE_CONTACT, bao.id)] == [
        "Followed up"
    ]
    assert [note.body for note in notes_service.list_for(db, NOTABLE_CONTACT, solo.id)] == [
        "Solo note"
    ]
    assert avery.company_id is not None
    assert [
        note.body for note in notes_service.list_for(db, NOTABLE_COMPANY, avery.company_id)
    ] == ["Shared vendor"]


def test_note_endpoints_round_trip(client, contact) -> None:
    created = client.post(
        "/api/v1/notes",
        json={"notableType": "contact", "notableId": str(contact.id), "body": "Called back"},
    )
    assert created.status_code == 201
    note_id = created.json()["data"]["id"]

    listed = client.get(
        "/api/v1/notes",
        params={"notableType": "contact", "notableId": str(contact.id)},
    )
    assert listed.status_code == 200
    assert listed.json()["data"][0]["body"] == "Called back"

    deleted = client.delete(f"/api/v1/notes/{note_id}")
    assert deleted.status_code == 200
    assert client.get(
        "/api/v1/notes",
        params={"notableType": "contact", "notableId": str(contact.id)},
    ).json()["data"] == []
