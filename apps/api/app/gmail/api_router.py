"""Session-protected Gmail endpoints under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.deps import DbSession, OAuthDep
from app.gmail.constants import CONN_NOT_CONNECTED, GMAIL_SETTINGS_SCOPE
from app.gmail.exceptions import GmailPermanentError
from app.gmail.schemas import GmailStatusDTO
from app.lib.response import data_body

router = APIRouter(tags=["gmail"])


@router.get("/gmail/status")
def gmail_status(request: Request, db: DbSession, oauth: OAuthDep) -> Response:
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
                display_name="",
                signature_html="",
                can_read_signature=False,
            )
        )

    scopes = row.scopes.split() if row.scopes else []
    connected = oauth.is_connected(db)
    can_read = connected and GMAIL_SETTINGS_SCOPE in scopes
    display_name = ""
    signature_html = ""
    if can_read and row.email:
        try:
            factory = getattr(request.app.state, "gmail_client_factory", None)
            client = factory(db) if factory is not None else oauth.client(db)
            send_as = client.get_send_as(row.email)
            display_name = send_as.display_name
            signature_html = send_as.signature
        except (GmailPermanentError, RuntimeError):
            can_read = False

    return data_body(
        GmailStatusDTO(
            connected=connected,
            configured=oauth.configured(),
            email=row.email,
            scopes=scopes,
            status=row.status,
            last_error=row.last_error,
            last_validated_at=row.last_validated_at,
            display_name=display_name,
            signature_html=signature_html,
            can_read_signature=can_read,
        )
    )


@router.post("/gmail/disconnect")
def gmail_disconnect(db: DbSession, oauth: OAuthDep) -> Response:
    oauth.disconnect(db)
    return data_body({"connected": False})
