"""Time, and the Brisbane calendar day the daily cap is measured against.

Every "now" in this app goes through a Clock so the cap can be tested without
patching the stdlib. Australia/Brisbane is UTC+10 year round with no DST, so the
calendar day rolls over at exactly 14:00 UTC — which is what makes the timezone
tests short and exact.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol
from zoneinfo import ZoneInfo

BRISBANE = ZoneInfo("Australia/Brisbane")


class Clock(Protocol):
    def now(self) -> dt.datetime:
        """Current time as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    def now(self) -> dt.datetime:
        return dt.datetime.now(dt.UTC)


def brisbane_date(clock: Clock) -> dt.date:
    """The Brisbane calendar date the daily counter is keyed on."""
    return clock.now().astimezone(BRISBANE).date()


def brisbane_day_bounds(day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    """[start, end) in UTC for one Brisbane calendar day, for range queries."""
    start = dt.datetime.combine(day, dt.time.min, tzinfo=BRISBANE)
    end = start + dt.timedelta(days=1)
    return start.astimezone(dt.UTC), end.astimezone(dt.UTC)


def ensure_aware(value: dt.datetime) -> dt.datetime:
    """Treat a naive datetime read back from the DB as UTC.

    Postgres timestamptz always round-trips aware through psycopg, but SQLite or
    a column defined without a timezone would not; this keeps comparisons from
    raising instead of silently misbehaving.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.UTC)
