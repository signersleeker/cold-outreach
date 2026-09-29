"""Schema migrations with explicit up/down.

Applied versions are recorded in `schema_migrations`. Table creates use
IF NOT EXISTS so an existing database (previously bootstrapped with
create_all) can adopt the migration history without recreating tables.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.migrations import versions


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    up: Callable[[Connection], None]
    down: Callable[[Connection], None]


def _discover() -> list[Migration]:
    found: list[Migration] = []
    for mod in versions.MODULES:
        found.append(
            Migration(
                version=mod.VERSION,
                name=mod.NAME,
                up=mod.up,
                down=mod.down,
            )
        )
    return sorted(found, key=lambda m: m.version)


MIGRATIONS: Sequence[Migration] = _discover()


def _ensure_bookkeeping(conn: Connection) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )


def applied_versions(conn: Connection) -> list[str]:
    _ensure_bookkeeping(conn)
    rows = conn.execute(
        text("SELECT version FROM schema_migrations ORDER BY version")
    ).fetchall()
    return [str(r[0]) for r in rows]


def pending(conn: Connection) -> list[Migration]:
    done = set(applied_versions(conn))
    return [m for m in MIGRATIONS if m.version not in done]


def status(engine: Engine) -> list[tuple[str, str, bool]]:
    """Return (version, name, applied) for every known migration."""
    with engine.begin() as conn:
        done = set(applied_versions(conn))
    return [(m.version, m.name, m.version in done) for m in MIGRATIONS]


def upgrade(engine: Engine, *, steps: int | None = None) -> list[str]:
    """Apply pending migrations in order. Returns versions applied."""
    applied: list[str] = []
    with engine.begin() as conn:
        todo = pending(conn)
        if steps is not None:
            todo = todo[: max(0, steps)]
        for migration in todo:
            migration.up(conn)
            conn.execute(
                text(
                    "INSERT INTO schema_migrations (version, name, applied_at) "
                    "VALUES (:version, :name, :applied_at)"
                ),
                {
                    "version": migration.version,
                    "name": migration.name,
                    "applied_at": datetime.now(UTC),
                },
            )
            applied.append(migration.version)
    return applied


def downgrade(engine: Engine, *, steps: int = 1) -> list[str]:
    """Roll back the most recently applied migrations. Returns versions removed."""
    if steps < 1:
        return []
    rolled: list[str] = []
    with engine.begin() as conn:
        done = applied_versions(conn)
        by_version = {m.version: m for m in MIGRATIONS}
        for version in reversed(done[-steps:]):
            migration = by_version.get(version)
            if migration is None:
                raise RuntimeError(
                    f"schema_migrations has {version!r} but no matching migration module"
                )
            migration.down(conn)
            conn.execute(
                text("DELETE FROM schema_migrations WHERE version = :version"),
                {"version": version},
            )
            rolled.append(version)
    return rolled
