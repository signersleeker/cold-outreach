"""Company location, filled from a CSV company_location column."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

VERSION = "0006"
NAME = "company_location"


def up(conn: Connection) -> None:
    conn.execute(
        text(
            "ALTER TABLE companies "
            "ADD COLUMN IF NOT EXISTS location VARCHAR(200) NOT NULL DEFAULT ''"
        )
    )


def down(conn: Connection) -> None:
    conn.execute(text("ALTER TABLE companies DROP COLUMN IF EXISTS location"))
