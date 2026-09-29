from __future__ import annotations

import datetime as dt
import uuid

from pydantic import Field

from app.lib.schemas import CamelModel


class SuppressionDTO(CamelModel):
    id: uuid.UUID
    email: str
    reason: str
    source: str
    created_at: dt.datetime


class SuppressionCreateRequest(CamelModel):
    email: str = Field(min_length=3, max_length=320)
    reason: str = "manual"
    source: str = ""
