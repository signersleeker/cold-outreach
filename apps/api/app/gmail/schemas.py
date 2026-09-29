from __future__ import annotations

import datetime as dt

from app.lib.schemas import CamelModel


class GmailStatusDTO(CamelModel):
    connected: bool
    configured: bool
    email: str
    scopes: list[str]
    status: str
    last_error: str
    last_validated_at: dt.datetime | None
    # Tokens are never included here, in any form.
    display_name: str = ""
    signature_html: str = ""
    # False when connected but the token lacks gmail.settings.basic — reconnect.
    can_read_signature: bool = False
