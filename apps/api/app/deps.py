"""FastAPI dependencies. Services live on app.state so tests can swap them."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.app_settings import service as settings_service
from app.app_settings.app_setting import AppSetting
from app.config import Settings, get_settings
from app.constants import SESSION_COOKIE_NAME
from app.database import get_db
from app.gmail.oauth_service import GmailOAuthService
from app.lib.clock import Clock
from app.lib.errors import AppError
from app.lib.session import read_session
from app.sends.services.send import SendService
from app.validation.base import EmailValidator


def app_settings_config(request: Request) -> Settings:
    return request.app.state.settings


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


def get_validator(request: Request) -> EmailValidator:
    return request.app.state.validator


def get_oauth(request: Request) -> GmailOAuthService:
    return request.app.state.gmail_oauth


def get_send_service(request: Request) -> SendService:
    return request.app.state.send_service


def require_session(request: Request) -> None:
    """Gate for every /api/v1 route.

    The public unsubscribe page and the OAuth callback deliberately do not use
    this — a recipient has no login, and Google cannot be asked for one.
    """
    settings = request.app.state.settings
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    if not read_session(settings.secret_key, token, settings.session_max_age_seconds):
        raise AppError(401, "not signed in")


def get_app_settings_row(db: Annotated[Session, Depends(get_db)]) -> AppSetting:
    return settings_service.get_or_create(db)


DbSession = Annotated[Session, Depends(get_db)]
ConfigDep = Annotated[Settings, Depends(app_settings_config)]
ClockDep = Annotated[Clock, Depends(get_clock)]
ValidatorDep = Annotated[EmailValidator, Depends(get_validator)]
OAuthDep = Annotated[GmailOAuthService, Depends(get_oauth)]
SendServiceDep = Annotated[SendService, Depends(get_send_service)]
SessionGuard = Depends(require_session)


def settings_dependency() -> Settings:
    """For code paths outside a request (CLI)."""
    return get_settings()
