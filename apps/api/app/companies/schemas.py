from __future__ import annotations

import datetime as dt
import uuid

from pydantic import Field

from app.lib.schemas import CamelModel


class CompanyDTO(CamelModel):
    id: uuid.UUID
    name: str
    website: str = ""
    linkedin_url: str = ""
    industry: str = ""
    size: str = ""
    location: str = ""
    contact_count: int = 0
    created_at: dt.datetime


class CompanyDetailDTO(CamelModel):
    id: uuid.UUID
    name: str
    website: str = ""
    linkedin_url: str = ""
    industry: str = ""
    size: str = ""
    location: str = ""
    created_at: dt.datetime
    updated_at: dt.datetime


class CompanyCreateRequest(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    website: str = Field(default="", max_length=500)
    linkedin_url: str = Field(default="", max_length=500)
    industry: str = Field(default="", max_length=80)
    size: str = Field(default="", max_length=16)
    location: str = Field(default="", max_length=200)


class CompanyPatchRequest(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    website: str | None = Field(default=None, max_length=500)
    linkedin_url: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=80)
    size: str | None = Field(default=None, max_length=16)
    location: str | None = Field(default=None, max_length=200)
