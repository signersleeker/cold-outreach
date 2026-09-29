"""Create tables and seed defaults. Idempotent — safe to re-run.

    python -m app.cli.seed
    python -m app.cli.seed --drop     # destroys all data first

No Alembic: the schema is created from the SQLAlchemy models, which is what the
brief asks for and is the right trade for a single-operator internal tool.
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv
from sqlalchemy import select

from app.app_settings.app_setting import SETTINGS_ID, AppSetting
from app.config import get_settings
from app.contacts.contact import Contact
from app.contacts.service import new_unsub_token
from app.database import Base, SessionLocal, get_engine, import_all_models, reset_engine
from app.templates.constants import (
    DEFAULT_COMPANY_LEGAL,
    DEFAULT_SENDER_NAME,
    DEFAULT_SENDER_TITLE,
    FIRST_TOUCH_BODY,
    FIRST_TOUCH_NAME,
    FIRST_TOUCH_SUBJECT,
    FOLLOW_UP_BODY,
    FOLLOW_UP_NAME,
    FOLLOW_UP_SUBJECT,
)
from app.templates.template import Template

_DEFAULT_TEMPLATES = (
    (FIRST_TOUCH_NAME, FIRST_TOUCH_SUBJECT, FIRST_TOUCH_BODY),
    (FOLLOW_UP_NAME, FOLLOW_UP_SUBJECT, FOLLOW_UP_BODY),
)


def _load_env() -> None:
    load_dotenv(".env", override=True)
    get_settings.cache_clear()
    reset_engine()


def seed(drop: bool = False) -> None:
    _load_env()
    import_all_models()
    engine = get_engine()

    if drop:
        print("dropping all tables…")
        Base.metadata.drop_all(engine)

    print("creating tables…")
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        row = db.get(AppSetting, SETTINGS_ID)
        if row is None:
            db.add(
                AppSetting(
                    id=SETTINGS_ID,
                    sender_name=DEFAULT_SENDER_NAME,
                    sender_title=DEFAULT_SENDER_TITLE,
                    company_legal=DEFAULT_COMPANY_LEGAL,
                    daily_cap=get_settings().daily_cap,
                )
            )
            print(
                f"seeded settings: {DEFAULT_SENDER_NAME} / {DEFAULT_SENDER_TITLE} / "
                f"{DEFAULT_COMPANY_LEGAL}, cap {get_settings().daily_cap}"
            )
        else:
            print("settings already present, left alone")

        for name, subject, body in _DEFAULT_TEMPLATES:
            if db.scalar(select(Template).where(Template.name == name)) is None:
                db.add(Template(name=name, subject=subject, body=body))
                print(f"seeded template: {name}")
            else:
                print(f"template already present: {name}")

        # Backfill unsub tokens for any row predating the column.
        backfilled = 0
        for contact in db.scalars(select(Contact).where(Contact.unsub_token == "")):
            contact.unsub_token = new_unsub_token()
            db.add(contact)
            backfilled += 1
        if backfilled:
            print(f"backfilled {backfilled} unsubscribe token(s)")

        db.commit()
    finally:
        db.close()

    print("done.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create tables and seed defaults.")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="drop every table first — destroys all contacts, sends and suppressions",
    )
    args = parser.parse_args()

    if args.drop:
        confirm = input("This deletes ALL data including suppressions. Type 'drop' to confirm: ")
        if confirm.strip() != "drop":
            print("aborted.")
            return 1

    seed(drop=args.drop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
