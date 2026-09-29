from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Query, Response, UploadFile

from app.constants import MAX_CSV_BYTES
from app.contacts import service
from app.contacts.constants import CONTACT_FILTERS
from app.contacts.csv_import import CsvFormatError
from app.contacts.schemas import (
    ContactCreateRequest,
    ContactDTO,
    ContactPatchRequest,
    ImportSummaryDTO,
    SuppressContactRequest,
)
from app.deps import ClockDep, DbSession, ValidatorDep
from app.lib.errors import AppError
from app.lib.response import data_body, list_body
from app.suppressions import service as suppressions_service
from app.suppressions.constants import REASONS

router = APIRouter(tags=["contacts"])


@router.get("/contacts")
def list_contacts(
    db: DbSession,
    q: str = Query(default=""),
    status: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Response:
    if status not in CONTACT_FILTERS:
        raise AppError(400, f"unknown filter {status!r}")
    rows, total = service.search(db, q=q, status=status, limit=limit, offset=offset)
    return list_body(
        [ContactDTO.model_validate(row) for row in rows],
        {"total": total, "limit": limit, "offset": offset},
    )


@router.post("/contacts")
def create_contact(
    payload: ContactCreateRequest, db: DbSession, validator: ValidatorDep, clock: ClockDep
) -> Response:
    contact = service.create(
        db,
        email=payload.email,
        validator=validator,
        clock=clock,
        first_name=payload.first_name,
        last_name=payload.last_name,
        company=payload.company,
        title=payload.title,
        hook=payload.hook,
        notes=payload.notes,
        source=payload.source,
    )
    return data_body(ContactDTO.model_validate(contact), status_code=201)


@router.post("/contacts/import")
async def import_contacts(
    db: DbSession,
    validator: ValidatorDep,
    clock: ClockDep,
    file: UploadFile = File(...),
) -> Response:
    content = await file.read()
    if not content:
        raise AppError(400, "the uploaded file is empty")
    if len(content) > MAX_CSV_BYTES:
        raise AppError(
            413, f"file is larger than {MAX_CSV_BYTES // 1024 // 1024} MB; split it up"
        )
    try:
        summary = service.import_csv(db, content, validator=validator, clock=clock)
    except CsvFormatError as exc:
        raise AppError(400, str(exc)) from exc
    return data_body(
        ImportSummaryDTO(
            created=summary.created,
            skipped_dupes=summary.skipped_dupes,
            invalid=summary.invalid,
            risky=summary.risky,
            valid=summary.valid,
            pending=summary.pending,
            missing_email=summary.missing_email,
            suppressed_existing=summary.suppressed_existing,
            truncated=summary.truncated,
            validator=summary.validator,
            headers_recognised=summary.headers_recognised,
        )
    )


@router.get("/contacts/{contact_id}")
def get_contact(contact_id: uuid.UUID, db: DbSession) -> Response:
    return data_body(ContactDTO.model_validate(service.require(db, contact_id)))


@router.patch("/contacts/{contact_id}")
def patch_contact(
    contact_id: uuid.UUID, payload: ContactPatchRequest, db: DbSession
) -> Response:
    changes = payload.model_dump(exclude_none=True)
    contact = service.update(db, contact_id, changes)
    return data_body(ContactDTO.model_validate(contact))


@router.delete("/contacts/{contact_id}")
def delete_contact(
    contact_id: uuid.UUID,
    db: DbSession,
    force: bool = Query(
        default=False,
        description="Required to delete a contact that has send history, which is deleted with it.",
    ),
) -> Response:
    return data_body(service.delete(db, contact_id, force=force))


@router.post("/contacts/{contact_id}/revalidate")
def revalidate_contact(
    contact_id: uuid.UUID, db: DbSession, validator: ValidatorDep, clock: ClockDep
) -> Response:
    contact = service.revalidate(db, contact_id, validator=validator, clock=clock)
    return data_body(ContactDTO.model_validate(contact))


@router.post("/contacts/{contact_id}/suppress")
def suppress_contact(
    contact_id: uuid.UUID,
    payload: SuppressContactRequest,
    db: DbSession,
    clock: ClockDep,
) -> Response:
    if payload.reason not in REASONS:
        raise AppError(400, f"unknown suppression reason {payload.reason!r}")
    contact = service.require(db, contact_id)
    suppressions_service.suppress(
        db,
        contact.email,
        reason=payload.reason,
        source=payload.note or "suppressed from contact list",
        now=clock.now(),
    )
    db.commit()
    db.refresh(contact)
    return data_body(ContactDTO.model_validate(contact))
