from datetime import datetime, timedelta, timezone

import pytest

from neuranova.config import load_settings
from neuranova.db import Store, _iso
from neuranova.models import EmailMessage, Triage
from neuranova.pa import briefing, business, proactive, quality

NOW = datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc)  # a Monday, inside working hours (UTC config)


@pytest.fixture
def env(tmp_path):
    settings = load_settings(tmp_path / "x.toml", env={})
    store = Store(":memory:", "neuranova", "owner")
    store.upsert_user("owner", "robin@neuranova.in", "Robin", "admin")
    store.upsert_user("u_priya", "priya@neuranova.in", "Priya", "member")
    return settings, store, store.pa


def backdate(pa, item_id, days):
    then = _iso(NOW - timedelta(days=days))
    pa.conn.execute("UPDATE items SET created_at = ?, updated_at = ? WHERE id = ?", (then, then, item_id))
    pa.conn.commit()


def test_briefing_sections_headline_and_ranked_actions(env):
    settings, store, pa = env
    pa.create_item("owner", kind="task", title="Sign vendor contract", priority="urgent")
    late = pa.create_item("owner", kind="task", title="Send fee structure to school", due_at=NOW - timedelta(days=1))
    pa.create_item("owner", kind="task", title="Prepare demo deck", due_at=NOW + timedelta(hours=3))
    pa.create_item("owner", kind="waiting", title="Documents from Asha", waiting_on="Asha", status="waiting",
                   due_at=NOW - timedelta(hours=5))
    pa.create_item("owner", kind="decision", title="Approve new mentor hiring")
    pa.create_item("owner", kind="qa_issue", title="Session join fails on Safari", status="ready_for_retest")
    hot = pa.create_item("owner", kind="lead", title="Admission enquiry from Meera", priority="high", stage="new")
    store.add_email(EmailMessage("gmail", "e1", "t1", "Tom <tom@x.example>", "Invoice question", "...",
                                 NOW - timedelta(days=1)))
    [e] = store.untriaged()
    store.save_triage(e["id"], Triage("client", "high", True, "Asks about invoice", "Reply"), NOW - timedelta(hours=2))
    for i in range(3):
        backdate(pa, pa.create_item("owner", kind="quality", title=f"Class started late #{i}",
                                    data={"category": "Scheduling"}), 2)

    b = briefing.build(store, settings, now=NOW, user_name="Robin Kumar")
    assert b["greeting"] == "Good morning, Robin"
    texts = {line["text"]: line["count"] for line in b["headline"]}
    assert texts["urgent item"] == 1 and texts["overdue item"] == 1 and texts["due today"] == 1
    assert texts["person has not delivered as promised"] == 1 and texts["waiting for your reply"] == 1
    assert texts["management decision pending"] == 1 and texts["application fix needs retesting"] == 1
    assert texts["recurring quality issue"] == 1 and texts["lead needs attention"] == 1
    assert [e["id"] for e in b["focus"]["overdue"]] == [late]
    assert [e["id"] for e in b["focus"]["opportunities"]] == [hot]
    first = b["actions"][0]
    assert first["text"] == "Reply to Tom" and "reply was due" in first["why"]     # breached promise ranks first
    joined = " | ".join(a["text"] for a in b["actions"])
    assert "Follow up with Asha" in joined and "Decide: Approve new mentor hiring" in joined


def test_quiet_day_is_all_clear(env):
    settings, store, _ = env
    b = briefing.build(store, settings, now=NOW)
    assert b["all_clear"] and b["headline"] == []


def test_lead_signals_and_pipeline(env):
    _, _, pa = env
    hot = pa.create_item("owner", kind="lead", title="Hot lead", priority="high", stage="contacted")
    stalled = pa.create_item("owner", kind="lead", title="Quiet lead", stage="quoted")
    backdate(pa, stalled, 12)
    won = pa.create_item("owner", kind="lead", title="Won lead", stage="converted", value=50000)
    lost = pa.create_item("owner", kind="lead", title="Lost lead", stage="lost", data={"lost_reason": "Price"})
    p = business.pipeline(pa, now=NOW + timedelta(seconds=1))
    assert [r["id"] for r in p["hot"]] == [hot] and [r["id"] for r in p["stalled"]] == [stalled]
    assert "at_risk" in p["signals"][stalled]
    assert p["conversion_pct"] == 50 and p["won_value"] == 50000 and p["lost_reasons"] == {"Price": 1}
    assert won and lost


def test_quality_patterns_need_three_in_window(env):
    _, _, pa = env
    for i in range(2):
        backdate(pa, pa.create_item("owner", kind="quality", title=f"Late {i}", data={"category": "Scheduling"}), 1)
    assert quality.patterns(pa, NOW) == []
    old = pa.create_item("owner", kind="quality", title="Old", data={"category": "Scheduling"})
    backdate(pa, old, 30)
    assert quality.patterns(pa, NOW) == []                                   # outside the 14-day window
    backdate(pa, pa.create_item("owner", kind="quality", title="Late 3", data={"category": "Scheduling"}), 3)
    [p] = quality.patterns(pa, NOW)
    assert p["category"] == "Scheduling" and p["count"] == 3 and "Management attention" in p["text"]


def test_proactive_digest_is_once_and_rate_limited(env):
    settings, store, pa = env
    sent = []
    notify = lambda text, teaser=None: sent.append(text)  # noqa: E731
    pa.create_item("owner", kind="waiting", title="Documents from Asha", waiting_on="Asha", status="waiting",
                   due_at=NOW - timedelta(hours=1))
    pa.create_item("owner", kind="task", title="Owned task overdue", owner_id="u_priya",
                   due_at=NOW - timedelta(hours=1))                          # owners get their own reminders
    assert proactive.run(store, settings, notify, now=NOW)["sent"] == 1
    assert "Asha hasn't delivered" in sent[0] and "Owned task" not in sent[0]
    assert proactive.run(store, settings, notify, now=NOW + timedelta(minutes=5))["sent"] == 0   # no repeats
    pa.create_item("owner", kind="task", title="New overdue thing", due_at=NOW)
    assert proactive.run(store, settings, notify, now=NOW + timedelta(minutes=10)) == {"sent": 0, "pending": 1}
    assert proactive.run(store, settings, notify, now=NOW + timedelta(minutes=70))["sent"] == 1  # after the gap
    night = NOW.replace(hour=23)
    pa.create_item("owner", kind="task", title="Not urgent", due_at=night - timedelta(hours=1))
    assert proactive.run(store, settings, notify, now=night)["sent"] == 0     # waits for working hours
    pa.create_item("owner", kind="task", title="Server down", priority="urgent", due_at=night - timedelta(minutes=5))
    assert proactive.run(store, settings, notify, now=night)["sent"] >= 1     # urgent goes out anyway
