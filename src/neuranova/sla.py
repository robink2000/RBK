"""Business-hours arithmetic for the response-time promise."""

from __future__ import annotations

from datetime import datetime, timedelta

from .config import WorkingHours


def _day_window(day: datetime, hours: WorkingHours) -> tuple[datetime, datetime]:
    start = day.replace(hour=hours.start.hour, minute=hours.start.minute, second=0, microsecond=0)
    end = day.replace(hour=hours.end.hour, minute=hours.end.minute, second=0, microsecond=0)
    return start, end


def add_business_time(start: datetime, amount: timedelta, hours: WorkingHours) -> datetime:
    """Return the moment `amount` of working time has elapsed after `start`.

    `start` must be timezone-aware and already in the workspace timezone.
    Time outside working hours (nights, weekends) does not count.
    """
    if not hours.days or hours.end <= hours.start:
        raise ValueError("working hours must cover at least one day with end after start")
    remaining = amount
    cursor = start
    while True:
        day_start, day_end = _day_window(cursor, hours)
        if cursor.weekday() in hours.days and cursor < day_end:
            cursor = max(cursor, day_start)
            available = day_end - cursor
            if remaining <= available:
                return cursor + remaining
            remaining -= available
        next_day = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        cursor = next_day


def reply_deadline(received_at: datetime, sla_hours: float, hours: WorkingHours, tz) -> datetime:
    return add_business_time(received_at.astimezone(tz), timedelta(hours=sla_hours), hours)
