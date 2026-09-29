"""The Brisbane calendar day, and the atomic counter keyed on it.

Australia/Brisbane is UTC+10 year round with no daylight saving, so the calendar
day always rolls over at exactly 14:00 UTC. These tests assert that constant
directly, which is what catches anyone swapping in Australia/Sydney (which does
observe DST and would drift by an hour for half the year).
"""

from __future__ import annotations

import datetime as dt

import pytest

from app.lib.clock import BRISBANE, brisbane_date, brisbane_day_bounds, ensure_aware
from app.sends.services.counters import (
    release_daily_slot,
    reserve_daily_slot,
    sends_today,
)
from tests.fakes import FrozenClock


def at(iso: str) -> FrozenClock:
    return FrozenClock(dt.datetime.fromisoformat(iso))


# ----------------------------------------------------------- the date boundary ----
def test_rollover_is_at_exactly_1400_utc() -> None:
    assert brisbane_date(at("2026-03-01T13:59:59+00:00")) == dt.date(2026, 3, 1)
    assert brisbane_date(at("2026-03-01T14:00:00+00:00")) == dt.date(2026, 3, 2)


def test_utc_midnight_is_already_mid_morning_in_brisbane() -> None:
    """00:00Z is 10:00 the same day locally — the dates agree here."""
    assert brisbane_date(at("2026-03-02T00:00:00+00:00")) == dt.date(2026, 3, 2)


def test_late_utc_evening_is_already_tomorrow_in_brisbane() -> None:
    assert brisbane_date(at("2026-03-01T23:30:00+00:00")) == dt.date(2026, 3, 2)


@pytest.mark.parametrize(
    "iso",
    [
        "2026-01-15T14:00:00+00:00",  # southern summer
        "2026-04-15T14:00:00+00:00",  # when Sydney leaves DST
        "2026-07-15T14:00:00+00:00",  # southern winter
        "2026-10-15T14:00:00+00:00",  # when Sydney enters DST
    ],
)
def test_boundary_does_not_move_across_the_year(iso: str) -> None:
    """Brisbane has no DST, so 14:00 UTC is the boundary in every month."""
    before = dt.datetime.fromisoformat(iso) - dt.timedelta(seconds=1)
    after = dt.datetime.fromisoformat(iso)
    assert brisbane_date(FrozenClock(before)) != brisbane_date(FrozenClock(after))


def test_offset_is_always_plus_ten() -> None:
    for month in range(1, 13):
        moment = dt.datetime(2026, month, 15, 12, 0, tzinfo=dt.UTC).astimezone(BRISBANE)
        assert moment.utcoffset() == dt.timedelta(hours=10), f"month {month}"


def test_a_non_utc_clock_is_converted_not_assumed() -> None:
    """13:00 in London on that date is 22:00 Brisbane — still the same day."""
    london = dt.datetime(2026, 3, 1, 13, 0, tzinfo=dt.timezone(dt.timedelta(hours=0)))
    assert brisbane_date(FrozenClock(london)) == dt.date(2026, 3, 1)


# -------------------------------------------------------------- day bounds ----
def test_day_bounds_span_exactly_24_hours_ending_at_1400_utc() -> None:
    start, end = brisbane_day_bounds(dt.date(2026, 3, 2))
    assert start == dt.datetime(2026, 3, 1, 14, 0, tzinfo=dt.UTC)
    assert end == dt.datetime(2026, 3, 2, 14, 0, tzinfo=dt.UTC)
    assert end - start == dt.timedelta(days=1)


def test_ensure_aware_treats_naive_as_utc() -> None:
    naive = dt.datetime(2026, 3, 2, 12, 0)
    assert ensure_aware(naive).tzinfo is dt.UTC
    already = dt.datetime(2026, 3, 2, 12, 0, tzinfo=dt.UTC)
    assert ensure_aware(already) is already


# --------------------------------------------------------- the atomic counter ----
DAY = dt.date(2026, 3, 2)
OTHER_DAY = dt.date(2026, 3, 3)


def test_first_reservation_of_the_day_creates_the_row(db) -> None:
    assert sends_today(db, DAY) == 0
    assert reserve_daily_slot(db, DAY, cap=20) == 1
    assert sends_today(db, DAY) == 1


def test_reservations_increment_up_to_the_cap(db) -> None:
    counts = [reserve_daily_slot(db, DAY, cap=3) for _ in range(3)]
    assert counts == [1, 2, 3]


def test_reservation_past_the_cap_returns_none_and_does_not_increment(db) -> None:
    for _ in range(3):
        reserve_daily_slot(db, DAY, cap=3)
    assert reserve_daily_slot(db, DAY, cap=3) is None
    assert sends_today(db, DAY) == 3, "a refused reservation must not increment"


def test_repeated_refusals_never_increment(db) -> None:
    reserve_daily_slot(db, DAY, cap=1)
    for _ in range(5):
        assert reserve_daily_slot(db, DAY, cap=1) is None
    assert sends_today(db, DAY) == 1


def test_a_lowered_cap_refuses_immediately(db) -> None:
    """The operator drops the cap below what has already gone out today."""
    for _ in range(10):
        reserve_daily_slot(db, DAY, cap=20)
    assert reserve_daily_slot(db, DAY, cap=5) is None
    assert sends_today(db, DAY) == 10, "already-sent count is never rewritten"


def test_release_gives_a_slot_back(db) -> None:
    reserve_daily_slot(db, DAY, cap=1)
    assert reserve_daily_slot(db, DAY, cap=1) is None
    assert release_daily_slot(db, DAY) == 0
    assert reserve_daily_slot(db, DAY, cap=1) == 1


def test_release_never_goes_negative(db) -> None:
    reserve_daily_slot(db, DAY, cap=5)
    for _ in range(5):
        release_daily_slot(db, DAY)
    assert sends_today(db, DAY) == 0


def test_release_on_a_day_with_no_row_is_a_no_op(db) -> None:
    assert release_daily_slot(db, DAY) is None


def test_adjacent_days_have_independent_counters(db) -> None:
    for _ in range(3):
        reserve_daily_slot(db, DAY, cap=3)
    assert reserve_daily_slot(db, DAY, cap=3) is None, "today is full"
    assert reserve_daily_slot(db, OTHER_DAY, cap=3) == 1, "tomorrow is not"
    assert sends_today(db, DAY) == 3


def test_the_cap_resets_when_the_brisbane_day_rolls_over(db) -> None:
    """Fill the cap at 13:59 UTC, advance one minute, and a fresh day begins."""
    clock = at("2026-03-01T13:59:00+00:00")
    day_one = brisbane_date(clock)
    for _ in range(2):
        reserve_daily_slot(db, day_one, cap=2)
    assert reserve_daily_slot(db, day_one, cap=2) is None

    clock.advance(minutes=1)
    day_two = brisbane_date(clock)
    assert day_two != day_one
    assert reserve_daily_slot(db, day_two, cap=2) == 1


def test_concurrent_reservations_never_exceed_the_cap(committed_db, engine) -> None:
    """Two real transactions racing on the same day.

    This needs genuine commits: the savepoint-based `db` fixture would serialise
    them on one connection and give a false pass. The ON CONFLICT row lock is
    what makes this correct at READ COMMITTED.
    """
    from sqlalchemy.orm import sessionmaker

    cap = 5
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    first, second = factory(), factory()
    granted = 0
    try:
        for _ in range(cap + 3):
            for session in (first, second):
                if reserve_daily_slot(session, DAY, cap=cap) is not None:
                    granted += 1
                session.commit()
    finally:
        first.close()
        second.close()

    assert granted == cap, f"granted {granted} slots for a cap of {cap}"
    assert sends_today(committed_db, DAY) == cap
