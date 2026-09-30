from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.app_settings.app_setting import SETTINGS_ID, AppSetting
from app.config import get_settings
from app.constants import HARD_MAX_DAILY_CAP
from app.lib.clock import DEFAULT_TIMEZONE, resolve_zone
from app.lib.errors import AppError
from app.templates.constants import (
    DEFAULT_COMPANY_LEGAL,
    DEFAULT_SENDER_NAME,
    DEFAULT_SENDER_TITLE,
)


def get_or_create(db: Session) -> AppSetting:
    row = db.get(AppSetting, SETTINGS_ID)
    if row is not None:
        return row
    row = AppSetting(
        id=SETTINGS_ID,
        sender_name=DEFAULT_SENDER_NAME,
        sender_title=DEFAULT_SENDER_TITLE,
        company_legal=DEFAULT_COMPANY_LEGAL,
        daily_cap=get_settings().daily_cap,
        timezone=DEFAULT_TIMEZONE,
        include_unsub_link=True,
    )
    db.add(row)
    db.flush()
    return row


def effective_daily_cap(db: Session) -> int:
    """The cap actually enforced, clamped to the server ceiling.

    The Settings page may store anything; this is what the send path uses, so a
    tampered or mistaken value can never lift the cap past HARD_MAX_DAILY_CAP.
    """
    stored = get_or_create(db).daily_cap
    return max(1, min(stored, HARD_MAX_DAILY_CAP))


def effective_timezone(db: Session) -> ZoneInfo:
    """IANA zone used for the daily cap and follow-up due dates."""
    return resolve_zone(get_or_create(db).timezone or DEFAULT_TIMEZONE)


def validate_timezone(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        raise AppError(400, "a timezone is required")
    try:
        ZoneInfo(stripped)
    except Exception as exc:
        raise AppError(400, f"unknown timezone {stripped!r}") from exc
    return stripped


def set_from_email(db: Session, email: str) -> AppSetting:
    """Record the connected mailbox address, read from the Gmail profile."""
    row = get_or_create(db)
    row.from_email = email
    db.add(row)
    return row


def identity_complete(row: AppSetting) -> bool:
    """Legal entity + connected From address. Display name comes from Gmail."""
    return bool(row.company_legal.strip() and row.from_email.strip())


def list_all(db: Session) -> AppSetting:
    return db.scalar(select(AppSetting).where(AppSetting.id == SETTINGS_ID)) or get_or_create(db)
