from __future__ import annotations

from fastapi import APIRouter, Response

from app.dashboard import service
from app.deps import ClockDep, DbSession, OAuthDep, SendServiceDep
from app.lib.response import data_body

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard(
    db: DbSession, clock: ClockDep, oauth: OAuthDep, sends: SendServiceDep
) -> Response:
    return data_body(service.build(db, clock=clock, oauth=oauth, sends=sends))
