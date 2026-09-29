from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.app_settings.app_setting import SETTINGS_ID, AppSetting
from app.config import get_settings
from app.constants import HARD_MAX_DAILY_CAP
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


def set_from_email(db: Session, email: str) -> AppSetting:
    """Record the connected mailbox address, read from the Gmail profile."""
    row = get_or_create(db)
    row.from_email = email
    db.add(row)
    return row


def identity_complete(row: AppSetting) -> bool:
    return bool(row.sender_name.strip() and row.company_legal.strip() and row.from_email.strip())


def list_all(db: Session) -> AppSetting:
    return db.scalar(select(AppSetting).where(AppSetting.id == SETTINGS_ID)) or get_or_create(db)
