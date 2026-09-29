"""Session-protected Gmail endpoints under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.deps import DbSession, OAuthDep
from app.gmail.constants import CONN_NOT_CONNECTED
from app.gmail.schemas import GmailStatusDTO
from app.lib.response import data_body

router = APIRouter(tags=["gmail"])


@router.get("/gmail/status")
def gmail_status(db: DbSession, oauth: OAuthDep) -> Response:
    row = oauth.current(db)
    if row is None:
        return data_body(
            GmailStatusDTO(
                connected=False,
                configured=oauth.configured(),
                email="",
                scopes=[],
                status=CONN_NOT_CONNECTED,
                last_error="",
                last_validated_at=None,
            )
        )
    return data_body(
        GmailStatusDTO(
            connected=oauth.is_connected(db),
            configured=oauth.configured(),
            email=row.email,
            scopes=row.scopes.split() if row.scopes else [],
            status=row.status,
            last_error=row.last_error,
            last_validated_at=row.last_validated_at,
        )
    )


@router.post("/gmail/disconnect")
def gmail_disconnect(db: DbSession, oauth: OAuthDep) -> Response:
    oauth.disconnect(db)
    return data_body({"connected": False})
