"""Store validation verdicts by email so a deleted contact can be re-imported."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

VERSION = "0005"
NAME = "email_validations"


def up(conn: Connection) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS email_validations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(320) NOT NULL UNIQUE,
                status VARCHAR(16) NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                validator VARCHAR(32) NOT NULL DEFAULT '',
                provider_status VARCHAR(64) NOT NULL DEFAULT '',
                provider_sub_status VARCHAR(64) NOT NULL DEFAULT '',
                provider_payload JSONB,
                validated_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT ck_email_validations_email_lower CHECK (email = lower(email)),
                CONSTRAINT ck_email_validations_status
                    CHECK (status IN ('valid', 'invalid', 'risky', 'unknown'))
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO email_validations (email, status, detail, validated_at)
            SELECT email, validation_status, validation_detail, validated_at
            FROM contacts
            WHERE validation_status <> 'pending'
              AND validated_at IS NOT NULL
            ON CONFLICT (email) DO NOTHING
            """
        )
    )


def down(conn: Connection) -> None:
    conn.execute(text("DROP TABLE IF EXISTS email_validations"))
