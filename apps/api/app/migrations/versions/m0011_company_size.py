"""Company size, filled from a CSV company_size column."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

VERSION = "0011"
NAME = "company_size"


def up(conn: Connection) -> None:
    conn.execute(
        text(
            "ALTER TABLE companies "
            "ADD COLUMN IF NOT EXISTS size VARCHAR(16) NOT NULL DEFAULT ''"
        )
    )


def down(conn: Connection) -> None:
    conn.execute(text("ALTER TABLE companies DROP COLUMN IF EXISTS size"))
