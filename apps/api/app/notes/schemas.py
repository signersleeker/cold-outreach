from __future__ import annotations

import datetime as dt
import uuid

from pydantic import Field

from app.lib.schemas import CamelModel
from app.notes.constants import MAX_NOTE_BODY


class NoteDTO(CamelModel):
    id: uuid.UUID
    notable_type: str
    notable_id: uuid.UUID
    body: str
    created_at: dt.datetime
    updated_at: dt.datetime


class NoteCreateRequest(CamelModel):
    notable_type: str
    notable_id: uuid.UUID
    body: str = Field(min_length=1, max_length=MAX_NOTE_BODY)
