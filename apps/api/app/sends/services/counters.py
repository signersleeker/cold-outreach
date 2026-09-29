"""The daily send counter.

The cap is the one invariant this app exists to hold, so reserving a slot is a
single atomic statement rather than a read followed by a write.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import text
from sqlalchemy.orm import Session

# Increment today's counter, but only while it is below the cap.
#
# Why this exact statement:
#   * One round trip, so there is no read-then-write window. `SELECT count; if
#     count < cap: UPDATE` is a TOCTOU race — two requests both read 19 and both
#     write 20.
#   * The WHERE on the DO UPDATE arm turns "at cap" into zero rows updated, so
#     RETURNING yields nothing and the caller sees None. Cap enforcement is a
#     property of the statement, not of application code.
#   * On conflict, Postgres blocks the second transaction on the existing row's
#     lock until the first commits, then re-evaluates the WHERE against the
#     committed value. Correct at READ COMMITTED; no advisory lock needed.
#   * The VALUES (…, 1) arm handles the first send of the day, so there is no
#     separate "create the row" bootstrap race.
_RESERVE_SQL = text(
    """
    INSERT INTO daily_counters (date, count)
    VALUES (:day, 1)
    ON CONFLICT (date) DO UPDATE
       SET count = daily_counters.count + 1
     WHERE daily_counters.count < :cap
    RETURNING count
    """
)

_RELEASE_SQL = text(
    """
    UPDATE daily_counters
       SET count = GREATEST(daily_counters.count - 1, 0)
     WHERE date = :day
    RETURNING count
    """
)

_COUNT_SQL = text("SELECT count FROM daily_counters WHERE date = :day")


def reserve_daily_slot(db: Session, day: dt.date, cap: int) -> int | None:
    """Consume one send slot for `day`.

    Returns the new count, or None when the cap is already reached.
    """
    return db.execute(_RESERVE_SQL, {"day": day, "cap": cap}).scalar_one_or_none()


def release_daily_slot(db: Session, day: dt.date) -> int | None:
    """Give a slot back. Only for failures where Gmail definitely never accepted."""
    return db.execute(_RELEASE_SQL, {"day": day}).scalar_one_or_none()


def sends_today(db: Session, day: dt.date) -> int:
    return db.execute(_COUNT_SQL, {"day": day}).scalar_one_or_none() or 0
