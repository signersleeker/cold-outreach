"""Company website and industry, template industry, and template groups."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

VERSION = "0004"
NAME = "company_profile_and_groups"


def up(conn: Connection) -> None:
    conn.execute(
        text(
            "ALTER TABLE companies "
            "ADD COLUMN IF NOT EXISTS website VARCHAR(500) NOT NULL DEFAULT ''"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE companies "
            "ADD COLUMN IF NOT EXISTS industry VARCHAR(80) NOT NULL DEFAULT ''"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE templates "
            "ADD COLUMN IF NOT EXISTS industry VARCHAR(80) NOT NULL DEFAULT ''"
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS template_groups (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(120) NOT NULL UNIQUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS template_group_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                group_id UUID NOT NULL REFERENCES template_groups (id) ON DELETE CASCADE,
                template_id UUID NOT NULL REFERENCES templates (id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                UNIQUE (group_id, template_id)
            )
            """
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_template_group_items_group_position "
            "ON template_group_items (group_id, position)"
        )
    )


def down(conn: Connection) -> None:
    conn.execute(text("DROP TABLE IF EXISTS template_group_items"))
    conn.execute(text("DROP TABLE IF EXISTS template_groups"))
    conn.execute(text("ALTER TABLE templates DROP COLUMN IF EXISTS industry"))
    conn.execute(text("ALTER TABLE companies DROP COLUMN IF EXISTS industry"))
    conn.execute(text("ALTER TABLE companies DROP COLUMN IF EXISTS website"))
