"""Regression tests for bugs found in the expert review (business logic)."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from neuranova.db import Store, row_dt
from neuranova.pa.dates import bucket, parse_deadline
from neuranova.pa.recurring import follow_on
from neuranova.pa.store import PAStore, data_of, similarity

IST = ZoneInfo("Asia/Kolkata")


def pa():
    return PAStore(Store(":memory:", "neuranova", "owner"))


def test_reclosing_a_repeating_item_makes_only_one_next():
    p = pa()
    item = p.create_item("owner", kind="task", title="Weekly report", due_at=datetime.now(IST) + timedelta(hours=1),
                         data={"repeat": "weekly", "tz": "Asia/Kolkata"})
    p.update_item(item, "owner", status="closed")
    p.update_item(item, "owner", status="open")
    p.update_item(item, "owner", status="closed")
    assert len(p.items(kind="task")) == 1


def test_verified_counts_as_completed():
    p = pa()
    item = p.create_item("owner", kind="qa_issue", title="Login bug")
    p.update_item(item, "QA", status="verified")
    assert p.item(item)["completed_at"]
    now = datetime.now(IST)
    assert [r["id"] for r in p.items_completed_between(now - timedelta(days=1), now + timedelta(minutes=1))] == [item]
    p.update_item(item, "QA", status="open")
    assert p.item(item)["completed_at"] is None


def test_monthly_repeat_keeps_its_day():
    p = pa()
    jan31 = datetime(2027, 1, 31, 9, tzinfo=IST)
    item = p.create_item("owner", kind="task", title="Rent", due_at=jan31, data={"repeat": "monthly", "tz": "Asia/Kolkata"})
    first = follow_on(p, p.item(item), "owner")
    assert data_of(p.item(first))["repeat"] == "monthly:31"


def test_dates_after_hours_and_number_before_month():
    evening = datetime(2026, 10, 6, 19, 0, tzinfo=IST)
    assert parse_deadline("finish it today", evening, end_of_day=time(18)) > evening
    assert parse_deadline("send 3 reports by 12 oct", evening).date().isoformat() == "2026-10-12"
    friday_morning = datetime(2026, 10, 9, 10, 0, tzinfo=IST)
    assert parse_deadline("by Friday", friday_morning).date() == friday_morning.date()
    assert bucket(datetime(2026, 10, 15, 12, tzinfo=IST), friday_morning) == "later"   # next Thursday isn't "this week"


def test_dedupe_tells_different_topics_apart():
    assert similarity("Call Asha about transport", "Call Asha about fees") < 0.6
    assert similarity("Asha to send documents", "Asha to send marksheet") < 0.6
    assert similarity("Send fee structure to Ravi's parents", "Send fee structure to Ravi's parents tomorrow") >= 0.8


def test_calendar_one_bad_address_does_not_hide_the_others():
    from neuranova.pa.calendar import fetch
    ics = ("BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:1\nDTSTART:20261007T100000Z\nDTEND:20261007T110000Z\n"
           "SUMMARY:Parent meeting\nEND:VEVENT\nEND:VCALENDAR\n")

    class Http:
        def get(self, url):
            if "bad" in url:
                raise RuntimeError("404")
            return type("R", (), {"text": ics, "raise_for_status": lambda s: None})()
    events = fetch(["https://bad/x.ics", "https://good/y.ics"], IST, http=Http(), now=datetime(2026, 10, 7, 8, tzinfo=IST))
    assert [e["title"] for e in events] == ["Parent meeting"]
