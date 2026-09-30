from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Query, Response

from app.dashboard import service
from app.deps import ClockDep, DbSession, OAuthDep, SendServiceDep
from app.lib.response import data_body, list_body

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/activity")
def get_activity(
    db: DbSession, clock: ClockDep, days: int = Query(default=30, ge=7, le=90)
) -> Response:
    return data_body(service.build_activity(db, clock=clock, days=days))


# Declared before /dashboard/sent so the static segment wins — FastAPI matches
# in declaration order.
@router.get("/dashboard/sent/calendar")
def get_sent_calendar(
    db: DbSession,
    clock: ClockDep,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
) -> Response:
    return data_body(service.build_sent_calendar(db, clock=clock, year=year, month=month))


@router.get("/dashboard/sent")
def get_sent_on(
    db: DbSession,
    date: dt.date = Query(...),
    limit: int = Query(default=200, ge=1, le=500),
) -> Response:
    emails = service.list_sent_on(db, day=date, limit=limit)
    return list_body(emails, {"total": len(emails), "date": date.isoformat()})


@router.get("/dashboard")
def get_dashboard(
    db: DbSession, clock: ClockDep, oauth: OAuthDep, sends: SendServiceDep
) -> Response:
    return data_body(service.build(db, clock=clock, oauth=oauth, sends=sends))
