from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from neuranova.db import Store, row_dt
from neuranova.pa import recurring
from neuranova.pa.store import PAStore, data_of

IST = ZoneInfo("Asia/Kolkata")
TUE = datetime(2026, 10, 6, 15, 0, tzinfo=IST)


@pytest.mark.parametrize("text, rule, title", [
    ("Send fee reminders every month on the 5th", "monthly:5", "Send fee reminders"),
    ("Payroll on the 28th of every month", "monthly:28", "Payroll"),
    ("Publish timetable every Friday", "weekly:4", "Publish timetable"),
    ("Gym on Mondays", "weekly:0", "Gym"),
    ("Check attendance every weekday", "weekdays", "Check attendance"),
    ("Parent newsletter every 2 weeks", "biweekly", "Parent newsletter"),
    ("Pay rent monthly", "monthly", "Pay rent"),
    ("Team standup daily at 10", "daily", "Team standup at 10"),
    ("Mondays meeting prep", None, "Mondays meeting prep"),
    ("Call Ravi tomorrow", None, "Call Ravi tomorrow"),
])
def test_parse(text, rule, title):
    assert recurring.parse(text) == (rule, title)


def test_dates():
    assert recurring.first_due("weekly:4", TUE, time(9)) == datetime(2026, 10, 9, 9, tzinfo=IST)
    assert recurring.first_due("daily", TUE, time(17)) == datetime(2026, 10, 6, 17, tzinfo=IST)   # later today
    assert recurring.first_due("monthly:5", TUE, time(9)) == datetime(2026, 11, 5, 9, tzinfo=IST)
    assert recurring.next_due("monthly:31", datetime(2026, 1, 31, 9, tzinfo=IST)) == datetime(2026, 2, 28, 9, tzinfo=IST)
    fri = datetime(2026, 10, 9, 18, tzinfo=IST)
    assert recurring.next_due("weekdays", fri) == datetime(2026, 10, 12, 18, tzinfo=IST)            # skips weekend
    assert recurring.describe("monthly:2") == "every month on the 2nd"


def test_closing_creates_the_next_one():
    pa = PAStore(Store(":memory:", "neuranova", "owner"))
    due = datetime.now(IST) + timedelta(hours=2)
    item = pa.create_item("owner", kind="task", title="Publish timetable", due_at=due, priority="high",
                          data={"repeat": "weekly:4", "tz": "Asia/Kolkata"})
    pa.update_item(item, "owner", status="closed")
    [nxt] = [r for r in pa.items(kind="task") if r["id"] != item]
    assert nxt["title"] == "Publish timetable" and nxt["priority"] == "high" and data_of(nxt)["repeat"] == "weekly:4"
    nxt_due = row_dt(nxt["due_at"]).astimezone(IST)
    assert nxt_due.weekday() == 4 and nxt_due > datetime.now(IST)
    pa.update_item(item, "owner", note="just a note")                    # no extra copies on other changes
    assert len(pa.items(kind="task")) == 1
    assert any("Next one created" in e["detail"] for e in pa.item_events(item))
