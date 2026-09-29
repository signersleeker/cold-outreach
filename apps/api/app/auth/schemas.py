from __future__ import annotations

from pydantic import Field

from app.lib.schemas import CamelModel


class LoginRequest(CamelModel):
    password: str = Field(min_length=1, max_length=512)


class SessionDTO(CamelModel):
    authenticated: bool
