"""Add settings.include_unsub_link."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

VERSION = "0002"
NAME = "include_unsub_link"


def up(conn: Connection) -> None:
    conn.execute(
        text(
            "ALTER TABLE settings "
            "ADD COLUMN IF NOT EXISTS include_unsub_link BOOLEAN NOT NULL DEFAULT true"
        )
    )


def down(conn: Connection) -> None:
    conn.execute(text("ALTER TABLE settings DROP COLUMN IF EXISTS include_unsub_link"))
