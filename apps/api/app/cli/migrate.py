"""Apply or roll back schema migrations.

    python -m app.cli.migrate up
    python -m app.cli.migrate up --steps 1
    python -m app.cli.migrate down
    python -m app.cli.migrate down --steps 1
    python -m app.cli.migrate status
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from app.config import get_settings
from app.database import get_engine, reset_engine
from app.migrations.runner import downgrade, status, upgrade


def _load_env() -> None:
    load_dotenv(".env", override=True)
    get_settings.cache_clear()
    reset_engine()


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply or roll back schema migrations.")
    sub = parser.add_subparsers(dest="command", required=True)

    up_p = sub.add_parser("up", help="apply pending migrations")
    up_p.add_argument(
        "--steps",
        type=int,
        default=None,
        help="apply at most N pending migrations (default: all)",
    )

    down_p = sub.add_parser("down", help="roll back the latest applied migration(s)")
    down_p.add_argument(
        "--steps",
        type=int,
        default=1,
        help="number of migrations to roll back (default: 1)",
    )

    sub.add_parser("status", help="list migrations and whether each is applied")

    args = parser.parse_args()
    _load_env()
    engine = get_engine()

    if args.command == "status":
        rows = status(engine)
        if not rows:
            print("no migrations registered")
            return 0
        width = max(len(v) for v, _, _ in rows)
        for version, name, applied in rows:
            mark = "applied" if applied else "pending"
            print(f"{version:<{width}}  {mark:<7}  {name}")
        return 0

    if args.command == "up":
        applied = upgrade(engine, steps=args.steps)
        if not applied:
            print("already up to date")
        else:
            for version in applied:
                print(f"applied {version}")
        return 0

    if args.command == "down":
        rolled = downgrade(engine, steps=args.steps)
        if not rolled:
            print("nothing to roll back")
        else:
            for version in rolled:
                print(f"rolled back {version}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
