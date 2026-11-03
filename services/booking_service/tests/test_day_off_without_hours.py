"""A day off counts even for a shop that never saved its weekly hours."""

from datetime import date, datetime, timedelta, timezone

from app.core.availability import HOLIDAY, NOT_CONFIGURED, Schedule, booking_problem, day_availability

DAY = date(2026, 11, 20)
START = datetime(2026, 11, 20, 6, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc)


def test_a_booking_on_a_day_off_is_refused():
    schedule = Schedule(configured=False, holidays={DAY: "Family function"})
    problem = booking_problem(schedule, START, 30, NOW, [], grace=timedelta(0))
    assert problem is not None and "closed" in problem and "Family function" in problem
    assert day_availability(schedule, DAY, 30, NOW, []).status == HOLIDAY


def test_other_days_stay_bookable_at_any_time():
    schedule = Schedule(configured=False, holidays={date(2026, 11, 21): None})
    assert booking_problem(schedule, START, 30, NOW, [], grace=timedelta(0)) is None
    assert day_availability(schedule, DAY, 30, NOW, []).status == NOT_CONFIGURED
