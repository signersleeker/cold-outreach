from __future__ import annotations

import datetime as dt
import uuid

from pydantic import Field

from app.lib.schemas import CamelModel


class TemplateDTO(CamelModel):
    id: uuid.UUID
    name: str
    subject: str
    body: str
    industry: str = ""
    created_at: dt.datetime
    updated_at: dt.datetime


class TemplateWithVarsDTO(TemplateDTO):
    referenced_vars: list[str]
    # Surfaced while editing, not while sending: a typo'd tag becomes a hard
    # blocker at send time, so it is far cheaper to point it out here.
    unknown_vars: list[str]


class TemplateCreateRequest(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)
    industry: str = Field(default="", max_length=80)


class TemplatePatchRequest(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    body: str | None = Field(default=None, min_length=1)
    industry: str | None = Field(default=None, max_length=80)


class TemplateGroupItemDTO(CamelModel):
    id: uuid.UUID
    position: int
    template_id: uuid.UUID
    template_name: str
    subject: str
    industry: str = ""
    delay_days: int = 0


class TemplateGroupItemInput(CamelModel):
    template_id: uuid.UUID
    delay_days: int = Field(default=0, ge=0, le=365)


class TemplateGroupDTO(CamelModel):
    id: uuid.UUID
    name: str
    items: list[TemplateGroupItemDTO]
    created_at: dt.datetime
    updated_at: dt.datetime


class TemplateGroupCreateRequest(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    items: list[TemplateGroupItemInput] = Field(min_length=1)


class TemplateGroupPatchRequest(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    items: list[TemplateGroupItemInput] | None = None
