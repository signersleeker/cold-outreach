from __future__ import annotations

import datetime as dt
import uuid

from pydantic import Field

from app.lib.schemas import CamelModel


class CompanyDTO(CamelModel):
    id: uuid.UUID
    name: str
    website: str = ""
    industry: str = ""
    contact_count: int = 0
    created_at: dt.datetime


class CompanyDetailDTO(CamelModel):
    id: uuid.UUID
    name: str
    website: str = ""
    industry: str = ""
    created_at: dt.datetime
    updated_at: dt.datetime


class CompanyCreateRequest(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    website: str = Field(default="", max_length=500)
    industry: str = Field(default="", max_length=80)


class CompanyPatchRequest(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    website: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=80)
