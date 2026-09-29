"""Initial schema.

Creates application tables only when they do not already exist, so a database
previously bootstrapped with SQLAlchemy create_all can adopt migrations safely.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

VERSION = "0001"
NAME = "initial"


def up(conn: Connection) -> None:
    # gen_random_uuid() is built into PostgreSQL 13+.
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                sender_name VARCHAR(120) NOT NULL DEFAULT '',
                sender_title VARCHAR(120) NOT NULL DEFAULT '',
                company_legal VARCHAR(200) NOT NULL DEFAULT '',
                from_email VARCHAR(320) NOT NULL DEFAULT '',
                reply_hint TEXT NOT NULL DEFAULT '',
                daily_cap INTEGER NOT NULL DEFAULT 20,
                last_inbox_sync_at TIMESTAMPTZ,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT ck_settings_singleton CHECK (id = 1)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(320) NOT NULL UNIQUE,
                first_name VARCHAR(120) NOT NULL DEFAULT '',
                last_name VARCHAR(120) NOT NULL DEFAULT '',
                company VARCHAR(200) NOT NULL DEFAULT '',
                title VARCHAR(200) NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                hook TEXT NOT NULL DEFAULT '',
                validation_status VARCHAR(16) NOT NULL DEFAULT 'pending',
                validation_detail TEXT NOT NULL DEFAULT '',
                validated_at TIMESTAMPTZ,
                suppressed BOOLEAN NOT NULL DEFAULT false,
                suppressed_reason VARCHAR(16) NOT NULL DEFAULT '',
                suppressed_at TIMESTAMPTZ,
                last_sent_at TIMESTAMPTZ,
                unsub_token VARCHAR(64) NOT NULL UNIQUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT ck_contacts_email_lower CHECK (email = lower(email))
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contacts_validation_status ON contacts (validation_status)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contacts_suppressed ON contacts (suppressed)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contacts_unsub_token ON contacts (unsub_token)"))

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS templates (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(120) NOT NULL UNIQUE,
                subject VARCHAR(300) NOT NULL,
                body TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(320) NOT NULL UNIQUE,
                refresh_token_encrypted TEXT NOT NULL DEFAULT '',
                access_token_encrypted TEXT NOT NULL DEFAULT '',
                token_expiry TIMESTAMPTZ,
                scopes TEXT NOT NULL DEFAULT '',
                status VARCHAR(16) NOT NULL DEFAULT 'not_connected',
                last_error TEXT NOT NULL DEFAULT '',
                last_validated_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS suppressions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(320) NOT NULL UNIQUE,
                reason VARCHAR(16) NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT ck_suppressions_email_lower CHECK (email = lower(email))
            )
            """
        )
    )

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS daily_counters (
                date DATE PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS send_events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                contact_id UUID NOT NULL REFERENCES contacts (id) ON DELETE CASCADE,
                template_id UUID REFERENCES templates (id) ON DELETE SET NULL,
                subject_rendered TEXT NOT NULL,
                body_rendered TEXT NOT NULL,
                rfc822_message_id VARCHAR(300) NOT NULL,
                gmail_message_id VARCHAR(64) NOT NULL DEFAULT '',
                status VARCHAR(16) NOT NULL DEFAULT 'queued',
                error TEXT NOT NULL DEFAULT '',
                sent_at TIMESTAMPTZ,
                settled_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_send_events_contact_created "
            "ON send_events (contact_id, created_at)"
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_send_events_status ON send_events (status)"))
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_send_events_rfc822_message_id "
            "ON send_events (rfc822_message_id)"
        )
    )


def down(conn: Connection) -> None:
    conn.execute(text("DROP TABLE IF EXISTS send_events"))
    conn.execute(text("DROP TABLE IF EXISTS daily_counters"))
    conn.execute(text("DROP TABLE IF EXISTS suppressions"))
    conn.execute(text("DROP TABLE IF EXISTS oauth_tokens"))
    conn.execute(text("DROP TABLE IF EXISTS templates"))
    conn.execute(text("DROP TABLE IF EXISTS contacts"))
    conn.execute(text("DROP TABLE IF EXISTS settings"))
