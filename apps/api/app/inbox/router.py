from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.deps import ClockDep, DbSession, OAuthDep
from app.inbox.schemas import InboxSyncSummaryDTO
from app.inbox.service import InboxSyncService
from app.lib.errors import AppError
from app.lib.response import data_body

router = APIRouter(tags=["inbox"])


@router.post("/inbox/sync")
def sync_inbox(
    request: Request, db: DbSession, oauth: OAuthDep, clock: ClockDep
) -> Response:
    if not oauth.is_connected(db):
        raise AppError(422, "connect a Gmail mailbox first")

    factory = getattr(request.app.state, "gmail_client_factory", None)
    client = factory(db) if factory is not None else oauth.client(db)

    summary = InboxSyncService(clock).sync(db, client)
    return data_body(
        InboxSyncSummaryDTO(
            scanned=summary.scanned,
            stops_found=summary.stops_found,
            bounces_found=summary.bounces_found,
            soft_bounces=summary.soft_bounces,
            auto_replies=summary.auto_replies,
            suppressed=summary.suppressed,
            errors=summary.errors,
        )
    )
