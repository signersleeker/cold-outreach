"""Per-step delays on template groups, and contact follow-up enrollments."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

VERSION = "0008"
NAME = "follow_up_plans"


def up(conn: Connection) -> None:
    conn.execute(
        text(
            "ALTER TABLE template_group_items "
            "ADD COLUMN IF NOT EXISTS delay_days INTEGER NOT NULL DEFAULT 0"
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS follow_up_enrollments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                contact_id UUID NOT NULL REFERENCES contacts (id) ON DELETE CASCADE,
                group_id UUID NOT NULL REFERENCES template_groups (id) ON DELETE CASCADE,
                status VARCHAR(16) NOT NULL DEFAULT 'active',
                assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                cancelled_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT ck_follow_up_enrollments_status CHECK (
                    status IN ('active', 'cancelled', 'completed')
                )
            )
            """
        )
    )
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_follow_up_enrollments_active_contact "
            "ON follow_up_enrollments (contact_id) WHERE status = 'active'"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_follow_up_enrollments_group "
            "ON follow_up_enrollments (group_id)"
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS follow_up_steps (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                enrollment_id UUID NOT NULL
                    REFERENCES follow_up_enrollments (id) ON DELETE CASCADE,
                group_item_id UUID
                    REFERENCES template_group_items (id) ON DELETE SET NULL,
                template_id UUID NOT NULL REFERENCES templates (id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                delay_days INTEGER NOT NULL DEFAULT 0,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                due_on DATE,
                sent_at TIMESTAMPTZ,
                send_event_id UUID REFERENCES send_events (id) ON DELETE SET NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT ck_follow_up_steps_status CHECK (
                    status IN ('pending', 'sent', 'cancelled')
                ),
                UNIQUE (enrollment_id, position)
            )
            """
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_follow_up_steps_due "
            "ON follow_up_steps (status, due_on) WHERE status = 'pending'"
        )
    )


def down(conn: Connection) -> None:
    conn.execute(text("DROP TABLE IF EXISTS follow_up_steps"))
    conn.execute(text("DROP TABLE IF EXISTS follow_up_enrollments"))
    conn.execute(
        text("ALTER TABLE template_group_items DROP COLUMN IF EXISTS delay_days")
    )
