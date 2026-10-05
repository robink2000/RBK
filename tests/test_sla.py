from datetime import timedelta

from conftest import utc
from neuranova.sla import add_business_time, reply_deadline


def test_within_same_day(settings):
    # Monday 10:00 + 4h -> Monday 14:00
    assert add_business_time(utc(2026, 10, 5, 10), timedelta(hours=4), settings.working_hours) == utc(2026, 10, 5, 14)


def test_rolls_over_to_next_morning(settings):
    # Monday 16:00 + 4h -> 2h Monday, 2h Tuesday -> Tuesday 11:00
    assert add_business_time(utc(2026, 10, 5, 16), timedelta(hours=4), settings.working_hours) == utc(2026, 10, 6, 11)


def test_night_and_weekend_do_not_count(settings):
    # Friday 22:00 -> clock starts Monday 09:00 -> Monday 13:00
    assert reply_deadline(utc(2026, 10, 9, 22), 4, settings.working_hours, settings.tz) == utc(2026, 10, 12, 13)
    # Saturday morning -> Monday 13:00
    assert reply_deadline(utc(2026, 10, 10, 8), 4, settings.working_hours, settings.tz) == utc(2026, 10, 12, 13)


def test_early_morning_starts_at_opening(settings):
    assert reply_deadline(utc(2026, 10, 6, 6), 4, settings.working_hours, settings.tz) == utc(2026, 10, 6, 13)
