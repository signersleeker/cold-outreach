from __future__ import annotations

from fastapi import APIRouter, Query, Response

from app.contacts.normalize import normalize_email
from app.deps import ClockDep, DbSession
from app.lib.errors import AppError
from app.lib.response import data_body, list_body
from app.suppressions import service
from app.suppressions.constants import REASONS
from app.suppressions.schemas import SuppressionCreateRequest, SuppressionDTO

router = APIRouter(tags=["suppressions"])


@router.get("/suppressions")
def list_suppressions(
    db: DbSession,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Response:
    rows = service.list_suppressions(db, limit=limit, offset=offset)
    return list_body(
        [SuppressionDTO.model_validate(row) for row in rows],
        {"total": service.count_all(db), "byReason": service.counts_by_reason(db)},
    )


@router.post("/suppressions")
def add_suppression(
    payload: SuppressionCreateRequest, db: DbSession, clock: ClockDep
) -> Response:
    email = normalize_email(payload.email)
    if not email:
        raise AppError(400, "a valid email address is required")
    if payload.reason not in REASONS:
        raise AppError(400, f"unknown suppression reason {payload.reason!r}")
    row = service.suppress(
        db, email, reason=payload.reason, source=payload.source or "added manually", now=clock.now()
    )
    db.commit()
    db.refresh(row)
    return data_body(SuppressionDTO.model_validate(row), status_code=201)


@router.delete("/suppressions/{email}")
def remove_suppression(email: str, db: DbSession) -> Response:
    """Remove a suppression.

    Only ever operator-initiated. Nothing in the app calls this automatically:
    an opt-out is not undone by a re-import or an inbox sync.
    """
    normalized = normalize_email(email)
    if not service.unsuppress(db, normalized):
        raise AppError(404, f"{normalized} is not on the suppression list")
    db.commit()
    return data_body({"deleted": True, "email": normalized})
