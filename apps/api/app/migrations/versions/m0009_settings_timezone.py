"""Configurable operator timezone for calendar days and the daily cap."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

VERSION = "0009"
NAME = "settings_timezone"


def up(conn: Connection) -> None:
    conn.execute(
        text(
            "ALTER TABLE settings "
            "ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) NOT NULL "
            "DEFAULT 'Australia/Brisbane'"
        )
    )


def down(conn: Connection) -> None:
    conn.execute(text("ALTER TABLE settings DROP COLUMN IF EXISTS timezone"))
