"""Add companies table and move contacts.company onto a nullable FK."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

VERSION = "0003"
NAME = "companies"


def up(conn: Connection) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(200) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    conn.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_name_lower ON companies (lower(name))")
    )

    conn.execute(
        text(
            """
            ALTER TABLE contacts
            ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies (id) ON DELETE SET NULL
            """
        )
    )
    conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_contacts_company_id ON contacts (company_id)")
    )

    has_company_col = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'contacts' AND column_name = 'company'
            """
        )
    ).scalar()
    if has_company_col:
        # One company per distinct non-blank name (case-insensitive). Keep the
        # first spelling seen by ordering on company within each lower(company).
        conn.execute(
            text(
                """
                INSERT INTO companies (name)
                SELECT src.name
                FROM (
                    SELECT DISTINCT ON (lower(company)) company AS name
                    FROM contacts
                    WHERE btrim(company) <> ''
                    ORDER BY lower(company), company
                ) AS src
                WHERE NOT EXISTS (
                    SELECT 1 FROM companies c WHERE lower(c.name) = lower(src.name)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE contacts AS ct
                SET company_id = co.id
                FROM companies AS co
                WHERE btrim(ct.company) <> ''
                  AND lower(ct.company) = lower(co.name)
                  AND ct.company_id IS NULL
                """
            )
        )
        conn.execute(text("ALTER TABLE contacts DROP COLUMN IF EXISTS company"))


def down(conn: Connection) -> None:
    conn.execute(
        text(
            """
            ALTER TABLE contacts
            ADD COLUMN IF NOT EXISTS company VARCHAR(200) NOT NULL DEFAULT ''
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE contacts AS ct
            SET company = co.name
            FROM companies AS co
            WHERE ct.company_id = co.id
            """
        )
    )
    conn.execute(text("ALTER TABLE contacts DROP COLUMN IF EXISTS company_id"))
    conn.execute(text("DROP TABLE IF EXISTS companies"))
