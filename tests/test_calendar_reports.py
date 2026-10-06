from datetime import datetime, timedelta, timezone

import httpx
import pytest

from neuranova.config import load_settings
from neuranova.db import Store
from neuranova.pa import calendar, reports

NOW = datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc)

ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:weekly-1
DTSTART:20260928T150000Z
DTEND:20260928T160000Z
RRULE:FREQ=WEEKLY;BYDAY=MO
SUMMARY:Admissions review with Meera
ATTENDEE;CN=Meera Iyer:mailto:meera@neuranova.in
END:VEVENT
BEGIN:VEVENT
UID:standup
DTSTART:20261005T083000Z
DTEND:20261005T090000Z
SUMMARY:Morning standup
END:VEVENT
BEGIN:VEVENT
UID:cancelled
DTSTART:20261005T170000Z
DTEND:20261005T180000Z
SUMMARY:Cancelled thing
STATUS:CANCELLED
END:VEVENT
BEGIN:VEVENT
UID:demo
DTSTART:20261007T100000Z
DTEND:20261007T110000Z
SUMMARY:Globex demo
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture
def env(tmp_path):
    settings = load_settings(tmp_path / "x.toml", env={})
    store = Store(":memory:", "neuranova", "owner")
    store.upsert_user("owner", "robin@neuranova.in", "Robin", "admin")
    return settings, store


def test_calendar_events_recurrence_and_cancelled(env):
    settings, _ = env
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=ICS)))
    events = calendar.fetch(["webcal://example/basic.ics"], settings.tz, http=http, now=NOW)
    titles = [e["title"] for e in events]
    weekly = [e for e in events if e["title"] == "Admissions review with Meera"]
    assert [e["start"][:10] for e in weekly] == ["2026-10-05"]               # this Monday, from the weekly series
    assert "Cancelled thing" not in titles and "Globex demo" in titles
    review = next(e for e in events if e["title"].startswith("Admissions") and e["start"].startswith("2026-10-05"))
    assert review["attendees"] == ["Meera Iyer"]


def test_meeting_prep_and_capture(env):
    settings, store = env
    pa = store.pa
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=ICS)))
    events = calendar.fetch(["https://example/basic.ics"], settings.tz, http=http, now=NOW)
    pa.create_item("owner", kind="lead", title="Admission enquiry from Meera's school", related_person="Meera Iyer")
    pa.create_item("owner", kind="task", title="Pay hosting invoice")
    view = calendar.meetings_view(pa, events, settings.tz, now=NOW.replace(hour=16, minute=30))
    review = next(m for m in view["today"] if m["title"].startswith("Admissions"))
    assert [p["title"] for p in review["prep"]] == ["Admission enquiry from Meera's school"]
    assert {m["title"] for m in view["needs_capture"]} == {"Morning standup", "Admissions review with Meera"}
    assert [m["title"] for m in view["upcoming"]] == ["Globex demo"]
    ids = calendar.capture_actions(pa, review, ["- Send fee sheet to Meera", "", "Book campus visit"], "owner")
    assert len(ids) == 2 and pa.item(ids[0])["related_project"] == "Admissions review with Meera"
    view = calendar.meetings_view(pa, events, settings.tz, now=NOW.replace(hour=16, minute=30))
    assert {m["title"] for m in view["needs_capture"]} == {"Morning standup"}


def test_bad_calendar_address_is_a_plain_error(env):
    settings, _ = env
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    with pytest.raises(RuntimeError, match="Couldn't read the calendar"):
        calendar.fetch(["https://example/nope.ics"], settings.tz, http=http)


class FakeLLM:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def text(self, system, user, **kw):
        self.calls.append((system, user))
        if self.fail:
            raise RuntimeError("AI down")
        return "*Weekly* all good"


@pytest.mark.parametrize("kind", list(reports.TITLES))
def test_every_report_builds_and_saves(env, kind):
    settings, store = env
    pa = store.pa
    pa.create_item("owner", kind="lead", title="Hot lead", priority="high", stage="contacted")
    pa.create_item("owner", kind="task", title="Overdue thing", due_at=NOW - timedelta(days=1))
    pa.create_item("owner", kind="qa_issue", title="Login slow", status="ready_for_retest", stage="retest")
    out = reports.generate(kind, store, settings, now=NOW)
    assert out["text"].startswith(f"*{reports.TITLES[kind]}*") and out["ai"] is False
    assert store.pa.report(out["id"])["kind"] == kind


def test_ai_writes_report_and_failure_falls_back(env):
    settings, store = env
    llm = FakeLLM()
    out = reports.generate("weekly", store, settings, llm=llm, goals="- grow", now=NOW)
    assert out["text"] == "*Weekly* all good" and out["ai"] and "Weekly Management Summary" in llm.calls[0][0]
    out = reports.generate("weekly", store, settings, llm=FakeLLM(fail=True), now=NOW)
    assert out["ai"] is False and out["text"].startswith("*Weekly Management Summary*")
