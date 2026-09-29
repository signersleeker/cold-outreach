from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response

from app.deps import DbSession, SendServiceDep
from app.lib.response import data_body, list_body
from app.sends.gates import GateFinding
from app.sends.schemas import (
    GateFindingDTO,
    SendEventDTO,
    SendPreviewDTO,
    SendPreviewRequest,
    SendRequest,
)
from app.sends.services.send import SendPreview

router = APIRouter(tags=["sends"])


def _finding(f: GateFinding) -> GateFindingDTO:
    return GateFindingDTO(code=f.code, message=f.message, requires_ack=f.requires_ack)


def _preview_dto(preview: SendPreview) -> SendPreviewDTO:
    return SendPreviewDTO(
        subject=preview.subject,
        body=preview.body,
        unsub_url=preview.unsub_url,
        from_email=preview.from_email,
        sends_today=preview.sends_today,
        daily_cap=preview.daily_cap,
        sendable=preview.result.ok,
        blockers=[_finding(f) for f in preview.result.blockers],
        warnings=[_finding(f) for f in preview.result.warnings],
        ack_required=list(preview.result.ack_required),
    )


@router.post("/sends/preview")
def preview_send(
    payload: SendPreviewRequest, db: DbSession, sends: SendServiceDep
) -> Response:
    preview = sends.preview(
        db,
        contact_id=payload.contact_id,
        template_id=payload.template_id,
        acknowledge=frozenset(payload.acknowledge),
    )
    return data_body(_preview_dto(preview))


@router.post("/sends")
def create_send(payload: SendRequest, db: DbSession, sends: SendServiceDep) -> Response:
    event = sends.send(
        db,
        contact_id=payload.contact_id,
        template_id=payload.template_id,
        acknowledge=frozenset(payload.acknowledge),
    )
    return data_body(SendEventDTO.model_validate(event), status_code=201)


@router.get("/sends")
def list_sends(
    db: DbSession,
    sends: SendServiceDep,
    contact_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> Response:
    events = sends.history(db, contact_id=contact_id, limit=limit)
    return list_body([SendEventDTO.model_validate(e) for e in events])
