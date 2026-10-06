"""Repeating items: "every Monday", "every weekday", "every month on the 5th".

The rule lives in the item's data ({"repeat": "weekly:0"}). When a repeating item is closed, the next one is
created with the next due date, so a missed week never silently drops the routine.

Rules: daily · weekdays · weekly · weekly:<0-6 Mon-Sun> · biweekly · monthly · monthly:<1-31>
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time, timedelta

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
SHORT = {d[:3]: i for i, d in enumerate(DAYS)}
CHOICES = [("", "Doesn't repeat"), ("daily", "Every day"), ("weekdays", "Every weekday (Mon-Fri)"),
           ("weekly", "Every week"), ("biweekly", "Every 2 weeks"), ("monthly", "Every month")]

_DAY = r"(monday|mon|tuesday|tues|tue|wednesday|wed|thursday|thurs|thur|thu|friday|fri|saturday|sat|sunday|sun)(?=s?\b)"


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def parse(text: str) -> tuple[str | None, str]:
    """(rule, text without the repeat words). Rule is None when the text doesn't repeat."""
    t = text
    patterns = [
        (rf"\b(?:every|each)\s+(?:2|two)\s+weeks?(?:\s+on\s+{_DAY})?|\bfortnightly\b", "biweekly"),
        (r"\b(?:every|each)\s+week\s*days?\b|\bevery\s+weekday\b|\bon\s+weekdays\b|\bweekdays\b", "weekdays"),
        (r"\b(?:every|each)\s+day\b|\bdaily\b", "daily"),
        (r"\b(?:on\s+the\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(?:every|each)\s+month\b|"
         r"\b(?:every|each)\s+month\s+on\s+(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\b|\bmonthly\s+on\s+(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\b",
         "monthly:n"),
        (r"\b(?:every|each)\s+month\b|\bmonthly\b", "monthly"),
        (rf"\b(?:every|each)\s+{_DAY}\b|\bweekly\s+on\s+{_DAY}\b|\bon\s+{_DAY}s\b", "weekly:day"),
        (r"\b(?:every|each)\s+week\b|\bweekly\b", "weekly"),
    ]
    for pattern, kind in patterns:
        m = re.search(pattern, t, re.I)
        if not m:
            continue
        rule = kind
        if kind == "weekly:day":
            day = next(g for g in m.groups() if g)
            rule = f"weekly:{SHORT[day[:3].lower()]}"
        elif kind == "biweekly":
            rule = "biweekly"
        elif kind == "monthly:n":
            n = int(next(g for g in m.groups() if g))
            if not 1 <= n <= 31:
                continue
            rule = f"monthly:{n}"
        cleaned = " ".join((t[:m.start()] + " " + t[m.end():]).split()).strip(" ,.-")
        return rule, cleaned or text
    return None, text


def describe(rule: str | None) -> str:
    if not rule:
        return ""
    if rule.startswith("weekly:"):
        return f"every {DAYS[int(rule.split(':')[1])].capitalize()}"
    if rule.startswith("monthly:"):
        return f"every month on the {_ordinal(int(rule.split(':')[1]))}"
    return {"daily": "every day", "weekdays": "every weekday", "weekly": "every week", "biweekly": "every 2 weeks",
            "monthly": "every month"}.get(rule, rule)


def _month_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def next_due(rule: str, after: datetime, at: time | None = None) -> datetime:
    """The first occurrence strictly after `after` (timezone-aware), at `at` (default: after's time)."""
    tz = after.tzinfo
    at = at or after.timetz().replace(tzinfo=None)
    d = after.date()

    def combine(day: date) -> datetime:
        return datetime.combine(day, at, tz)

    def first_after(candidates) -> datetime:
        for day in candidates:
            if combine(day) > after:
                return combine(day)
        raise ValueError(rule)

    days = (d + timedelta(days=i) for i in range(0, 400))
    if rule == "daily":
        return first_after(days)
    if rule == "weekdays":
        return first_after(x for x in days if x.weekday() < 5)
    if rule.startswith("weekly:"):
        wd = int(rule.split(":")[1])
        return first_after(x for x in days if x.weekday() == wd)
    if rule == "weekly":
        return combine(d + timedelta(days=7))
    if rule == "biweekly":
        return combine(d + timedelta(days=14))
    if rule.startswith("monthly"):
        want = int(rule.split(":")[1]) if ":" in rule else d.day
        y, m = d.year, d.month
        for _ in range(14):
            candidate = _month_day(y, m, want)
            if combine(candidate) > after:
                return combine(candidate)
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    raise ValueError(f"Unknown repeat rule {rule}")


def _allows(rule: str, day: date) -> bool:
    if rule == "weekdays":
        return day.weekday() < 5
    if rule.startswith("weekly:"):
        return day.weekday() == int(rule.split(":")[1])
    if rule.startswith("monthly:"):
        want = int(rule.split(":")[1])
        return day == _month_day(day.year, day.month, want)
    return True


def first_due(rule: str, now: datetime, at: time) -> datetime:
    """When a new repeating item is first due: today if the rule allows it and the time is still ahead."""
    today = datetime.combine(now.date(), at, now.tzinfo)
    if _allows(rule, now.date()) and today > now:
        return today
    if rule in ("weekly", "biweekly", "monthly"):     # no fixed day: start tomorrow, then keep the rhythm
        return today + timedelta(days=1)
    return next_due(rule, today, at)


def follow_on(store_pa, row, actor: str) -> int | None:
    """Create the next occurrence after a repeating item is closed. Returns the new item id."""
    import json
    from zoneinfo import ZoneInfo

    from ..db import row_dt
    data = json.loads(row["data"] or "{}")
    rule = data.get("repeat")
    if not rule:
        return None
    try:
        tz = ZoneInfo(data.get("tz") or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")
    base = row_dt(row["due_at"]).astimezone(tz) if row["due_at"] else datetime.now(tz)
    nxt = next_due(rule, base, base.timetz().replace(tzinfo=None))
    now = datetime.now(tz)
    while nxt <= now:                       # closed late: skip to the next one still ahead
        nxt = next_due(rule, nxt, nxt.timetz().replace(tzinfo=None))
    new_id = store_pa.create_item(
        actor, kind=row["kind"], title=row["title"], description=row["description"], department=row["department"],
        owner_id=row["owner_id"], priority=row["priority"], related_person=row["related_person"],
        related_project=row["related_project"], contact_id=row["contact_id"], source=row["source"] or "manual",
        status="waiting" if row["kind"] == "waiting" else "open", due_at=nxt, data=data)
    store_pa._event(row["id"], "PA", "note", f"Next one created: #{new_id}, due {nxt:%a %d %b %H:%M}")
    store_pa.conn.commit()
    return new_id
