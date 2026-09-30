from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response

from app.deps import DbSession
from app.lib.response import data_body, list_body
from app.notes import service
from app.notes.schemas import NoteCreateRequest, NoteDTO

router = APIRouter(tags=["notes"])


@router.get("/notes")
def list_notes(
    db: DbSession,
    notable_type: str = Query(alias="notableType"),
    notable_id: uuid.UUID = Query(alias="notableId"),
) -> Response:
    notes = service.list_for(db, notable_type, notable_id)
    return list_body(
        [NoteDTO.model_validate(note) for note in notes],
        {"total": len(notes)},
    )


@router.post("/notes")
def create_note(payload: NoteCreateRequest, db: DbSession) -> Response:
    note = service.create(
        db,
        notable_type=payload.notable_type,
        notable_id=payload.notable_id,
        body=payload.body,
    )
    return data_body(NoteDTO.model_validate(note), status_code=201)


@router.delete("/notes/{note_id}")
def delete_note(note_id: uuid.UUID, db: DbSession) -> Response:
    service.delete(db, note_id)
    return data_body({"deleted": True})
