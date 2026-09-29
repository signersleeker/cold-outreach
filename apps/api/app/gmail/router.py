"""Root-mounted OAuth redirect pair.

These are NOT under /api/v1 because the redirect URI is registered with Google
and is part of the app's public URL surface:

    http://localhost:8000/auth/google/callback

/auth/google requires a session — only the operator may start a connect flow.
/auth/google/callback cannot require one: it is entered by Google's redirect, so
its authenticity comes from the HMAC-signed `state` parameter instead.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse

from app.deps import DbSession, OAuthDep, require_session
from app.lib.errors import AppError

router = APIRouter(tags=["gmail-oauth"])


@router.get("/auth/google", dependencies=[Depends(require_session)])
def start_google_oauth(oauth: OAuthDep) -> RedirectResponse:
    if not oauth.configured():
        raise AppError(
            503,
            "Gmail OAuth is not configured. Set GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET and SECRET_KEY in apps/api/.env.",
        )
    return RedirectResponse(url=oauth.authorization_url(), status_code=302)


@router.get("/auth/google/callback")
def google_oauth_callback(
    request: Request,
    db: DbSession,
    oauth: OAuthDep,
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
) -> RedirectResponse:
    frontend = request.app.state.settings.resolved_frontend_url()
    if error:
        from urllib.parse import quote

        return RedirectResponse(
            url=f"{frontend}/settings?gmail=error&message={quote(error)}", status_code=302
        )
    return RedirectResponse(url=oauth.handle_callback(db, code, state), status_code=302)
