"""Migration runner: up/down and IF NOT EXISTS behaviour."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.migrations.runner import applied_versions, downgrade, status, upgrade


def test_upgrade_is_idempotent(engine: Engine) -> None:
    first = upgrade(engine)
    second = upgrade(engine)
    assert second == []
    # Session fixture already applied migrations; first may be empty too.
    assert isinstance(first, list)


def test_status_lists_every_migration(engine: Engine) -> None:
    rows = status(engine)
    versions = [v for v, _, _ in rows]
    assert versions == ["0001", "0002", "0003"]
    assert all(applied for _, _, applied in rows)


def test_downgrade_one_step_removes_companies(engine: Engine) -> None:
    upgrade(engine)
    assert "companies" in inspect(engine).get_table_names()

    rolled = downgrade(engine, steps=1)
    assert rolled == ["0003"]
    assert "companies" not in inspect(engine).get_table_names()
    assert "company" in {c["name"] for c in inspect(engine).get_columns("contacts")}

    # Re-apply so later tests still see the full schema.
    upgrade(engine)
    assert "companies" in inspect(engine).get_table_names()
    assert "company_id" in {c["name"] for c in inspect(engine).get_columns("contacts")}


def test_initial_up_skips_existing_tables(engine: Engine) -> None:
    """CREATE TABLE IF NOT EXISTS must not wipe an already-populated settings row."""
    upgrade(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO settings (id, sender_name, company_legal, daily_cap) "
                "VALUES (1, 'Keep Me', 'Acme', 7) "
                "ON CONFLICT (id) DO UPDATE SET sender_name = EXCLUDED.sender_name, "
                "company_legal = EXCLUDED.company_legal, daily_cap = EXCLUDED.daily_cap"
            )
        )

    # Force re-run of 0001's up by rolling all the way down then up again —
    # but only after checking IF NOT EXISTS path via calling 0001.up directly
    # while tables exist would wipe nothing. Downgrade all then upgrade is fine;
    # instead call up on 0001 while applied and tables exist by rolling to
    # before 0001... that drops tables. So: call m0001.up again while current.
    from app.migrations.versions import m0001_initial

    with engine.begin() as conn:
        m0001_initial.up(conn)
        name = conn.execute(text("SELECT sender_name FROM settings WHERE id = 1")).scalar()
    assert name == "Keep Me"


def test_companies_migration_backfills_existing_names(engine: Engine) -> None:
    """Downgrade past companies, seed a string company, upgrade and check the FK."""
    upgrade(engine)
    downgrade(engine, steps=1)
    assert "company" in {c["name"] for c in inspect(engine).get_columns("contacts")}

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contacts (email, company, unsub_token) VALUES "
                "('a@northwind.example', 'Northwind', 'tok-a'), "
                "('b@northwind.example', 'northwind', 'tok-b'), "
                "('c@solo.example', '', 'tok-c')"
            )
        )

    upgrade(engine)
    with engine.begin() as conn:
        names = [
            r[0]
            for r in conn.execute(text("SELECT name FROM companies ORDER BY lower(name)")).fetchall()
        ]
        assert names == ["Northwind"]
        linked = conn.execute(
            text("SELECT email, company_id IS NOT NULL FROM contacts ORDER BY email")
        ).fetchall()
        assert linked == [
            ("a@northwind.example", True),
            ("b@northwind.example", True),
            ("c@solo.example", False),
        ]
        shared = conn.execute(
            text(
                "SELECT count(DISTINCT company_id) FROM contacts WHERE company_id IS NOT NULL"
            )
        ).scalar()
        assert shared == 1


def test_full_downgrade_and_upgrade_round_trip(engine: Engine) -> None:
    upgrade(engine)
    with engine.begin() as conn:
        before = applied_versions(conn)

    rolled = downgrade(engine, steps=len(before))
    assert set(rolled) == set(before)

    inspector = inspect(engine)
    assert "settings" not in inspector.get_table_names()
    assert "contacts" not in inspector.get_table_names()

    applied = upgrade(engine)
    assert applied == ["0001", "0002", "0003"]
    assert "settings" in inspect(engine).get_table_names()
    assert "companies" in inspect(engine).get_table_names()
    assert "include_unsub_link" in {c["name"] for c in inspect(engine).get_columns("settings")}
