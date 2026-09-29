from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.gmail.constants import CONN_NOT_CONNECTED


class OAuthToken(Base):
    """The one connected Gmail mailbox.

    Tokens are AES-GCM encrypted with a key derived from SECRET_KEY and are never
    returned by any API response.
    """

    __tablename__ = "oauth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)

    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    token_expiry: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    scopes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=CONN_NOT_CONNECTED
    )
    last_error: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    last_validated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
