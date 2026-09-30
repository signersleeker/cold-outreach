"""Polymorphic notes for contacts and companies."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

VERSION = "0007"
NAME = "notes"


def up(conn: Connection) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                notable_type VARCHAR(16) NOT NULL,
                notable_id UUID NOT NULL,
                body TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT ck_notes_notable_type CHECK (
                    notable_type IN ('contact', 'company')
                )
            )
            """
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_notes_notable ON notes (notable_type, notable_id)"
        )
    )


def down(conn: Connection) -> None:
    conn.execute(text("DROP TABLE IF EXISTS notes"))
