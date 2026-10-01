"""Company LinkedIn URL, filled from a CSV company_linkedin_url column."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

VERSION = "0010"
NAME = "company_linkedin"


def up(conn: Connection) -> None:
    conn.execute(
        text(
            "ALTER TABLE companies "
            "ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(500) NOT NULL DEFAULT ''"
        )
    )


def down(conn: Connection) -> None:
    conn.execute(text("ALTER TABLE companies DROP COLUMN IF EXISTS linkedin_url"))
