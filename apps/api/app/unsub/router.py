"""Public unsubscribe endpoint. No session, no login, no JavaScript.

GET  /u/{token}  renders a confirmation page.
POST /u/{token}  performs the suppression.

The split is deliberate. Mail clients and corporate security gateways prefetch
and scan links in received mail; a GET that suppressed on sight would remove
prospects who never clicked. Requiring a POST makes the link safe to scan while
still being one click for a real person.

Every failure mode — unknown token, malformed token, already used — renders the
same neutral page with HTTP 200, so this endpoint cannot be used to enumerate
which tokens are real.
"""

from __future__ import annotations

import threading
from time import monotonic

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.app_settings import service as settings_service
from app.contacts import service as contacts_service
from app.deps import ClockDep, DbSession
from app.suppressions import service as suppressions_service
from app.suppressions.constants import REASON_UNSUB
from app.unsub.pages import confirm_page, done_page, invalid_page

router = APIRouter(tags=["unsub"])

_RATE_LIMIT_PER_MINUTE = 30
_WINDOW_SECONDS = 60.0
_hits: dict[str, list[float]] = {}
_hits_lock = threading.Lock()


def _rate_limited(key: str) -> bool:
    """Crude per-IP limit. This is the only unauthenticated route that hits the DB."""
    with _hits_lock:
        now = monotonic()
        recent = [t for t in _hits.get(key, []) if now - t < _WINDOW_SECONDS]
        recent.append(now)
        _hits[key] = recent
        return len(recent) > _RATE_LIMIT_PER_MINUTE


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _invalid() -> HTMLResponse:
    return HTMLResponse(invalid_page(), status_code=200)


@router.get("/u/{token}", response_class=HTMLResponse)
def unsub_confirm(token: str, request: Request, db: DbSession) -> HTMLResponse:
    if _rate_limited(_client_key(request)):
        return _invalid()

    contact = contacts_service.by_unsub_token(db, token)
    if contact is None:
        return _invalid()

    company = settings_service.get_or_create(db).company_legal
    db.commit()

    if suppressions_service.is_suppressed(db, contact.email) is not None:
        return HTMLResponse(done_page(contact.email, company))
    return HTMLResponse(confirm_page(contact.email, company, contact.unsub_token))


@router.post("/u/{token}", response_class=HTMLResponse)
def unsub_submit(
    token: str, request: Request, db: DbSession, clock: ClockDep
) -> HTMLResponse:
    if _rate_limited(_client_key(request)):
        return _invalid()

    contact = contacts_service.by_unsub_token(db, token)
    if contact is None:
        return _invalid()

    suppressions_service.suppress(
        db,
        contact.email,
        reason=REASON_UNSUB,
        source=f"unsub page ({token[:8]}…)",
        now=clock.now(),
    )
    company = settings_service.get_or_create(db).company_legal
    db.commit()
    return HTMLResponse(done_page(contact.email, company))
