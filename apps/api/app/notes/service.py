from __future__ import annotations

import uuid

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.companies.company import Company
from app.contacts.contact import Contact
from app.lib.errors import AppError
from app.notes.constants import MAX_NOTE_BODY, NOTABLE_CONTACT, NOTABLE_TYPES
from app.notes.note import Note


def _require_type(notable_type: str) -> str:
    if notable_type not in NOTABLE_TYPES:
        raise AppError(400, f"unknown note target {notable_type!r}")
    return notable_type


def _require_body(body: str) -> str:
    text = body.strip()
    if not text:
        raise AppError(400, "a note cannot be empty")
    if len(text) > MAX_NOTE_BODY:
        raise AppError(400, f"a note cannot be longer than {MAX_NOTE_BODY} characters")
    return text


def _require_parent(db: Session, notable_type: str, notable_id: uuid.UUID) -> None:
    if notable_type == NOTABLE_CONTACT:
        if db.get(Contact, notable_id) is None:
            raise AppError(404, "contact not found")
        return
    if db.get(Company, notable_id) is None:
        raise AppError(404, "company not found")


def list_for(db: Session, notable_type: str, notable_id: uuid.UUID) -> list[Note]:
    _require_type(notable_type)
    _require_parent(db, notable_type, notable_id)
    return list(
        db.scalars(
            select(Note)
            .where(Note.notable_type == notable_type, Note.notable_id == notable_id)
            .order_by(Note.created_at.desc(), Note.id.desc())
        )
    )


def create(db: Session, *, notable_type: str, notable_id: uuid.UUID, body: str) -> Note:
    _require_type(notable_type)
    text = _require_body(body)
    _require_parent(db, notable_type, notable_id)
    note = Note(notable_type=notable_type, notable_id=notable_id, body=text)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def add(
    db: Session,
    *,
    notable_type: str,
    notable_id: uuid.UUID,
    body: str,
    skip_duplicate: bool = False,
) -> Note | None:
    """Attach a note without committing. A blank body is ignored.

    ``skip_duplicate`` drops a note whose text is already stored on that parent.
    CSV company notes repeat on every row of the same company.
    """
    text = body.strip()
    if not text:
        return None
    _require_type(notable_type)
    if skip_duplicate:
        # autoflush is off, so a note added earlier in this import is invisible
        # until it is written.
        db.flush()
        existing = db.scalar(
            select(Note.id).where(
                Note.notable_type == notable_type,
                Note.notable_id == notable_id,
                Note.body == text,
            )
        )
        if existing is not None:
            return None
    note = Note(notable_type=notable_type, notable_id=notable_id, body=text)
    db.add(note)
    return note


def delete(db: Session, note_id: uuid.UUID) -> None:
    note = db.get(Note, note_id)
    if note is None:
        raise AppError(404, "note not found")
    db.delete(note)
    db.commit()


def delete_for(db: Session, notable_type: str, notable_id: uuid.UUID) -> None:
    """Remove every note on a parent. The caller commits."""
    db.execute(
        sql_delete(Note).where(
            Note.notable_type == notable_type, Note.notable_id == notable_id
        )
    )
