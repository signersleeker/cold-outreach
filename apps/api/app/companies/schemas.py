from __future__ import annotations

import datetime as dt
import uuid

from pydantic import Field

from app.lib.schemas import CamelModel


class CompanyDTO(CamelModel):
    id: uuid.UUID
    name: str
    contact_count: int = 0
    created_at: dt.datetime


class CompanyDetailDTO(CamelModel):
    id: uuid.UUID
    name: str
    created_at: dt.datetime
    updated_at: dt.datetime


class CompanyCreateRequest(CamelModel):
    name: str = Field(min_length=1, max_length=200)
