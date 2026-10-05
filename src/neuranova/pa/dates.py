"""Turn everyday deadline phrases into datetimes, without an AI call.

Handles: today, tonight, EOD / end of day, tomorrow, day after tomorrow, this week / end of week,
next week, next <weekday>, (by|before|on) <weekday>, month-end, in N days/hours/weeks,
"12 Oct", "Oct 12", "12/10" (day first), "2026-10-12", plus an optional time ("3pm", "15:30",
"at 10"). Phrases that depend on other context ("before the meeting") return None so the AI or
the user can decide.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time, timedelta

WEEKDAYS = {name: i for i, names in enumerate([
    ("monday", "mon"), ("tuesday", "tue", "tues"), ("wednesday", "wed"), ("thursday", "thu", "thur", "thurs"),
    ("friday", "fri"), ("saturday", "sat"), ("sunday", "sun")]) for name in names}
MONTHS = {name: i for i in range(1, 13) for name in (calendar.month_name[i].lower(), calendar.month_abbr[i].lower())}
MONTHS["sept"] = 9

TIME_RE = re.compile(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|\b(?:at\s+)?([01]?\d|2[0-3]):([0-5]\d)\b|\bat\s+(\d{1,2})\b",
                     re.I)


def _time_of(text: str) -> time | None:
    m = TIME_RE.search(text)
    if not m:
        return None
    if m.group(1):
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if m.group(3).lower() == "pm" else 0)
        return time(hour, minute)
    if m.group(4):
        return time(int(m.group(4)), int(m.group(5)))
    hour = int(m.group(6))
    if hour > 23:
        return None
    return time(hour + 12 if 1 <= hour <= 7 else hour, 0)  # "at 3" in business talk means 3 pm


def _next_weekday(today: date, weekday: int, strictly_next_week: bool = False) -> date:
    ahead = (weekday - today.weekday()) % 7
    if strictly_next_week:
        start_next_week = today + timedelta(days=7 - today.weekday())
        return start_next_week + timedelta(days=weekday)
    return today + timedelta(days=ahead or 7) if ahead == 0 else today + timedelta(days=ahead)


def parse_deadline(text: str, now: datetime, start_of_day: time = time(9, 0),
                   end_of_day: time = time(18, 0)) -> datetime | None:
    """`now` must be timezone-aware in the workspace timezone. Returns an aware datetime or None."""
    if not text or not text.strip():
        return None
    s = " " + re.sub(r"\s+", " ", text.lower().strip()) + " "
    tz = now.tzinfo
    today = now.date()
    at = _time_of(s)

    def build(day: date, default: time) -> datetime:
        return datetime.combine(day, at or default, tz)

    if re.search(r"\b(context|meeting|demo|call|review)\b", s) and re.search(r"\b(before|after) the\b", s):
        return None
    if re.search(r"\b(asap|immediately|right away|urgent(ly)?)\b", s):
        return now + timedelta(hours=2)
    if m := re.search(r"\bin (\d+|an?|one|two|three) (hour|hours|hr|hrs|day|days|week|weeks)\b", s):
        n = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3}.get(m.group(1)) or int(m.group(1))
        unit = m.group(2)
        if unit.startswith("h"):
            return now + timedelta(hours=n)
        return build(today + timedelta(days=n * (7 if unit.startswith("week") else 1)), end_of_day)
    if m := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s):
        try:
            return build(date(int(m.group(1)), int(m.group(2)), int(m.group(3))), end_of_day)
        except ValueError:
            return None
    if m := re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3,9})\b|\b([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?\b", s):
        day_s, mon_s = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        if mon_s in MONTHS:
            month, day_n = MONTHS[mon_s], int(day_s)
            year = today.year
            try:
                d = date(year, month, day_n)
                if d < today - timedelta(days=30):
                    d = date(year + 1, month, day_n)
                return build(d, end_of_day)
            except ValueError:
                return None
    if m := re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", s):
        day_n, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else today.year
        year += 2000 if year < 100 else 0
        try:
            d = date(year, month, day_n)
            if not m.group(3) and d < today - timedelta(days=30):
                d = date(year + 1, month, day_n)
            return build(d, end_of_day)
        except ValueError:
            return None
    if re.search(r"\bday after tomorrow\b", s):
        return build(today + timedelta(days=2), end_of_day)
    if re.search(r"\b(tomorrow|tmrw|tmr)\b", s):
        return build(today + timedelta(days=1), start_of_day if "morning" in s else end_of_day)
    if re.search(r"\btonight\b", s):
        return build(today, time(20, 0))
    if re.search(r"\b(eod|cob|end of (the )?day|today|by evening|this evening)\b", s):
        return build(today, end_of_day)
    if re.search(r"\b(month[- ]end|end of (the )?month)\b", s):
        return build(date(today.year, today.month, calendar.monthrange(today.year, today.month)[1]), end_of_day)
    if re.search(r"\bnext month\b", s):
        first = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
        return build(first, start_of_day)
    if re.search(r"\b(this week|end of (the )?week|eow|by weekend)\b", s):
        friday = today + timedelta(days=(4 - today.weekday()) % 7)
        return build(friday, end_of_day)
    for name, idx in sorted(WEEKDAYS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\bnext {name}\b", s):
            return build(_next_weekday(today, idx, strictly_next_week=True), start_of_day)
        if re.search(rf"\bbefore {name}\b", s):
            # "before Friday" = done by the start of Friday's working day
            return build(_next_weekday(today, idx), start_of_day)
        if re.search(rf"\b(by|on|this|coming)?\s*{name}\b", s):
            return build(_next_weekday(today, idx), end_of_day)
    if re.search(r"\bnext week\b", s):
        return build(_next_weekday(today, 0, strictly_next_week=True), start_of_day)
    if at is not None:
        candidate = datetime.combine(today, at, tz)
        return candidate if candidate > now else candidate + timedelta(days=1)
    return None


def bucket(due: datetime | None, now: datetime) -> str:
    """overdue | today | tomorrow | this_week | later | none (all in `now`'s timezone)."""
    if due is None:
        return "none"
    due = due.astimezone(now.tzinfo)
    if due < now:
        return "overdue"
    days = (due.date() - now.date()).days
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if due.date() <= now.date() + timedelta(days=6 - now.weekday()) or days < 7:
        return "this_week"
    return "later"
