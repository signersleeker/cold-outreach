from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile

from app.companies.constants import resolve_industry_filter
from app.constants import MAX_CSV_BYTES
from app.contacts import assignments, service
from app.contacts.constants import CONTACT_FILTERS
from app.contacts.csv_import import CsvFormatError, parse_mapping_json, preview_csv
from app.contacts.schemas import (
    ContactCreateRequest,
    ContactDTO,
    ContactPatchRequest,
    ContactStatsDTO,
    GroupAssignmentPreviewRequest,
    GroupAssignmentRequest,
    ImportPreviewDTO,
    ImportSummaryDTO,
    SuppressContactRequest,
)
from app.deps import ClockDep, DbSession, SendServiceDep, ValidatorDep
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
    company_id: uuid.UUID | None = Query(default=None, alias="companyId"),
    industry: str = Query(default=""),
    group: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Response:
    if status not in CONTACT_FILTERS:
        raise AppError(400, f"unknown filter {status!r}")
    rows, total = service.search(
        db,
        q=q,
        status=status,
        company_id=company_id,
        industry=resolve_industry_filter(industry),
        group=service.resolve_group_filter(db, group),
        limit=limit,
        offset=offset,
    )
    return list_body(
        [ContactDTO.model_validate(row) for row in rows],
        {"total": total, "limit": limit, "offset": offset},
    )


# Declared before /contacts/{contact_id} — FastAPI matches in declaration order,
# so the dynamic route would otherwise swallow "stats" as a contact id.
@router.get("/contacts/stats")
def contact_stats(
    db: DbSession,
    q: str = Query(default=""),
    company_id: uuid.UUID | None = Query(default=None, alias="companyId"),
    industry: str = Query(default=""),
    group: str = Query(default=""),
) -> Response:
    return data_body(
        ContactStatsDTO(
            **service.stats(
                db,
                q=q,
                company_id=company_id,
                industry=resolve_industry_filter(industry),
                group=service.resolve_group_filter(db, group),
            )
        )
    )


def _assignment_kwargs(payload: GroupAssignmentRequest | GroupAssignmentPreviewRequest) -> dict:
    return {
        "contact_ids": payload.contact_ids,
        "all_matching": payload.all_matching,
        "q": payload.q,
        "status": payload.status,
        "industry": payload.industry,
        "group": payload.group,
        "acknowledge": frozenset(payload.acknowledge),
    }


@router.post("/contacts/group-assignments/preview")
def preview_group_assignment(
    payload: GroupAssignmentPreviewRequest, db: DbSession, sends: SendServiceDep
) -> Response:
    result = assignments.preview(
        db, sends, group_id=payload.group_id, **_assignment_kwargs(payload)
    )
    return data_body(result)


@router.post("/contacts/group-assignments")
def apply_group_assignment(
    payload: GroupAssignmentRequest, db: DbSession, sends: SendServiceDep, clock: ClockDep
) -> Response:
    result = assignments.apply(
        db,
        sends,
        clock=clock,
        group_id=payload.group_id,
        **_assignment_kwargs(payload),
    )
    return data_body(result)


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


def _read_upload(content: bytes) -> None:
    if not content:
        raise AppError(400, "the uploaded file is empty")
    if len(content) > MAX_CSV_BYTES:
        raise AppError(
            413, f"file is larger than {MAX_CSV_BYTES // 1024 // 1024} MB; split it up"
        )


def _form_flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@router.post("/contacts/import/preview")
async def preview_import(file: UploadFile = File(...)) -> Response:
    content = await file.read()
    _read_upload(content)
    try:
        preview = preview_csv(content)
    except CsvFormatError as exc:
        raise AppError(400, str(exc)) from exc
    return data_body(
        ImportPreviewDTO(headers=preview.headers, suggestions=preview.suggestions)
    )


@router.post("/contacts/import")
async def import_contacts(
    db: DbSession,
    validator: ValidatorDep,
    clock: ClockDep,
    file: UploadFile = File(...),
    mapping: str | None = Form(default=None),
    skip_validation: Annotated[str, Form(alias="skipValidation")] = "false",
) -> Response:
    content = await file.read()
    _read_upload(content)
    try:
        column_map = parse_mapping_json(mapping)
        summary = service.import_csv(
            db,
            content,
            validator=validator,
            clock=clock,
            column_map=column_map,
            skip_validation=_form_flag(skip_validation),
        )
    except CsvFormatError as exc:
        raise AppError(400, str(exc)) from exc
    return data_body(
        ImportSummaryDTO(
            created=summary.created,
            skipped_dupes=summary.skipped_dupes,
            skipped_existing_company=summary.skipped_existing_company,
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
