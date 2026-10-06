from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from neuranova.db import Store
from neuranova.pa.dates import bucket, parse_deadline
from neuranova.pa.store import PAStore, similarity

IST = ZoneInfo("Asia/Kolkata")
MON = datetime(2026, 10, 5, 11, 0, tzinfo=IST)


@pytest.mark.parametrize("phrase, expected", [
    ("tomorrow", "Tue 06 Oct 18:00"), ("EOD", "Mon 05 Oct 18:00"), ("end of day", "Mon 05 Oct 18:00"),
    ("next Monday", "Mon 12 Oct 09:00"), ("before Friday", "Fri 09 Oct 09:00"), ("by Friday", "Fri 09 Oct 18:00"),
    ("next week", "Mon 12 Oct 09:00"), ("by month-end", "Sat 31 Oct 18:00"), ("Friday 3pm", "Fri 09 Oct 15:00"),
    ("12 Oct", "Mon 12 Oct 18:00"), ("Oct 20 at 10:30", "Tue 20 Oct 10:30"), ("15/10", "Thu 15 Oct 18:00"),
    ("in 3 days", "Thu 08 Oct 18:00"), ("tomorrow morning", "Tue 06 Oct 09:00"), ("this week", "Fri 09 Oct 18:00"),
])
def test_deadline_phrases(phrase, expected):
    assert parse_deadline(phrase, MON).strftime("%a %d %b %H:%M") == expected


def test_context_phrases_are_left_to_the_ai():
    assert parse_deadline("before the meeting", MON) is None
    assert parse_deadline("whenever you can", MON) is None


def test_buckets():
    assert bucket(MON - timedelta(hours=1), MON) == "overdue"
    assert bucket(MON + timedelta(hours=2), MON) == "today"
    assert bucket(MON + timedelta(days=1), MON) == "tomorrow"
    assert bucket(MON + timedelta(days=3), MON) == "this_week"
    assert bucket(MON + timedelta(days=20), MON) == "later"
    assert bucket(None, MON) == "none"


@pytest.fixture
def pa():
    store = Store(":memory:", "neuranova", "owner")
    store.upsert_user("owner", "robin@neuranova.in", "Robin", "admin")
    return PAStore(store)


def test_items_history_and_completion(pa):
    item_id = pa.create_item("owner", kind="task", title="Complete testing before Friday", department="QA",
                             owner_id="owner", due_at=MON + timedelta(days=3), priority="high", source="email")
    pa.update_item(item_id, "owner", status="in_progress")
    pa.update_item(item_id, "owner", note="Halfway done")
    pa.update_item(item_id, "owner", status="closed")
    row = pa.item(item_id)
    assert row["completed_at"] and row["owner_name"] == "Robin"
    events = [e["event"] for e in pa.item_events(item_id)]
    assert events == ["created", "updated", "note", "updated"]
    pa.update_item(item_id, "owner", status="open")
    assert pa.item(item_id)["completed_at"] is None                      # reopened
    assert [r["id"] for r in pa.items(status="active")] == [item_id]


def test_duplicate_detection(pa):
    pa.create_item("owner", kind="waiting", title="Documents from Asha Rao", related_person="Asha Rao")
    assert similarity("Waiting for documents from Asha", "Documents from Asha Rao") > 0.4
    hit = pa.similar_open("documents from Asha Rao for admission", kind="waiting", person="Asha Rao", threshold=0.5)
    assert hit is not None
    assert pa.similar_open("Pay hosting invoice", kind="waiting") is None


def test_contacts_are_remembered_by_email_or_phone(pa):
    a = pa.contact_for(name="Asha Rao", email="Asha@Acme.example", role="parent")
    b = pa.contact_for(email="asha@acme.example", phone="+91 98765 43210")
    assert a == b
    c = pa.contact_for(phone="919876543210")
    assert c == a and pa.contact(a)["role"] == "parent" and pa.contact(a)["phone"] == "919876543210"


def test_team_tasks_move_into_items():
    store = Store(":memory:", "neuranova", "owner")
    store.upsert_user("owner", "robin@neuranova.in", "Robin", "admin")
    store.conn.execute(
        """INSERT INTO team_tasks (workspace_id, title, notes, assignee_id, created_by, status, created_at)
           VALUES ('neuranova', 'Old board task', 'from phase 4', 'owner', 'owner', 'blocked', ?)""",
        (datetime.now(timezone.utc).isoformat(),))
    store.conn.commit()
    [row] = store.pa.items(status="active")
    assert row["title"] == "Old board task" and row["status"] == "blocked"
    PAStore(store)                                                        # runs only once
    assert len(store.pa.items(status=None)) == 1
