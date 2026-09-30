from __future__ import annotations

from fastapi import APIRouter, Query, Response

from app.dashboard import service
from app.deps import ClockDep, DbSession, OAuthDep, SendServiceDep
from app.lib.response import data_body

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/activity")
def get_activity(
    db: DbSession, clock: ClockDep, days: int = Query(default=30, ge=7, le=90)
) -> Response:
    return data_body(service.build_activity(db, clock=clock, days=days))


@router.get("/dashboard")
def get_dashboard(
    db: DbSession, clock: ClockDep, oauth: OAuthDep, sends: SendServiceDep
) -> Response:
    return data_body(service.build(db, clock=clock, oauth=oauth, sends=sends))
