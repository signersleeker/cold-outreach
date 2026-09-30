"""Time, and the operator calendar day the daily cap is measured against.

Every "now" in this app goes through a Clock so the cap can be tested without
patching the stdlib. Calendar days (daily cap, follow-up due dates, activity
buckets) use the IANA timezone stored in Settings — not the viewer's browser.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Default for new installs and for code paths that have no Session yet.
DEFAULT_TIMEZONE = "Australia/Brisbane"


class Clock(Protocol):
    def now(self) -> dt.datetime:
        """Current time as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    def now(self) -> dt.datetime:
        return dt.datetime.now(dt.UTC)


def resolve_zone(name: str) -> ZoneInfo:
    """Return a ZoneInfo, falling back to the default if the name is invalid."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, KeyError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def local_date(clock: Clock, tz: ZoneInfo | str) -> dt.date:
    """The calendar date in ``tz`` that the daily counter is keyed on."""
    zone = tz if isinstance(tz, ZoneInfo) else resolve_zone(tz)
    return clock.now().astimezone(zone).date()


def day_bounds(day: dt.date, tz: ZoneInfo | str) -> tuple[dt.datetime, dt.datetime]:
    """[start, end) in UTC for one calendar day in ``tz``, for range queries."""
    zone = tz if isinstance(tz, ZoneInfo) else resolve_zone(tz)
    start = dt.datetime.combine(day, dt.time.min, tzinfo=zone)
    end = start + dt.timedelta(days=1)
    return start.astimezone(dt.UTC), end.astimezone(dt.UTC)


def date_in_zone(moment: dt.datetime, tz: ZoneInfo | str) -> dt.date:
    """Calendar date of an instant in ``tz``."""
    zone = tz if isinstance(tz, ZoneInfo) else resolve_zone(tz)
    return ensure_aware(moment).astimezone(zone).date()


def ensure_aware(value: dt.datetime) -> dt.datetime:
    """Treat a naive datetime read back from the DB as UTC.

    Postgres timestamptz always round-trips aware through psycopg, but SQLite or
    a column defined without a timezone would not; this keeps comparisons from
    raising instead of silently misbehaving.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.UTC)
