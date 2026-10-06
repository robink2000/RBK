from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from neuranova.db import Store
from neuranova.pa.comms import Incoming, apply_analysis, process_message
from neuranova.pa.store import PAStore
from test_jobs import LEAD, FakeBrain, FakeMail, FakeNotifier, email, recent

IST = ZoneInfo("Asia/Kolkata")
EOD = datetime(2026, 1, 1, 18).time()


def op(**kw):
    base = {"op": "create", "item_id": None, "kind": "task", "title": "", "description": "", "department": "Operations",
            "priority": "medium", "due_iso": None, "due_text": None, "owner_hint": None, "waiting_on": None,
            "related_person": None, "related_project": None, "next_action": "", "lead_stage": None,
            "quality_category": None, "qa_stage": None, "value": None, "reason": "test"}
    return {**base, **kw}


def result(*ops, importance="medium", signals=("action_required",), **kw):
    return {"summary": "s", "importance": importance, "signals": list(signals), "sender_name": kw.get("name"),
            "sender_role": kw.get("role", "other"), "organization": None, "needs_reply": False,
            "operations": list(ops)}


class FakeLLM:
    def __init__(self, *results):
        self.results, self.calls = list(results), []

    def json(self, system, user, schema, **kw):
        self.calls.append(user)
        return self.results.pop(0)


@pytest.fixture
def pa():
    store = Store(":memory:", "neuranova", "owner")
    store.upsert_user("owner", "robin@neuranova.in", "Robin", "admin")
    store.upsert_user("u_priya", "priya@neuranova.in", "Priya Shah", "member")
    return PAStore(store)


def msg(pa, body, channel="whatsapp", sender="Asha Rao", phone="919876543210"):
    cid = pa.contact_for(name=sender, phone=phone)
    return Incoming(channel, "m1", sender, "", body, datetime.now(timezone.utc), contact_id=cid)


def test_commitment_becomes_waiting_with_expected_date(pa):
    m = msg(pa, "I will send the documents tomorrow.")
    out = apply_analysis(pa, result(op(kind="waiting", title="Documents from Asha Rao", waiting_on="Asha Rao",
                                       related_person="Asha Rao", due_text="tomorrow"), name="Asha Rao", role="parent"),
                         m, tz=IST, end_of_day=EOD)
    [row] = pa.items()
    assert row["kind"] == "waiting" and row["status"] == "waiting" and row["waiting_on"] == "Asha Rao"
    due = datetime.fromisoformat(row["due_at"]).astimezone(IST)
    assert due.date() == (datetime.now(IST) + timedelta(days=1)).date() and due.hour == 18
    assert pa.contact(m.contact_id)["role"] == "parent" and out.applied[0]["op"] == "create"


def test_duplicate_create_becomes_update_and_delivery_closes(pa):
    m = msg(pa, "Sending docs soon")
    apply_analysis(pa, result(op(kind="waiting", title="Documents from Asha Rao", related_person="Asha Rao")), m,
                   tz=IST, end_of_day=EOD)
    out = apply_analysis(pa, result(op(kind="waiting", title="Documents from Asha Rao for admission",
                                       related_person="Asha Rao", due_text="Friday")), m, tz=IST, end_of_day=EOD)
    assert out.applied[0]["op"] == "update" and len(pa.items()) == 1
    item_id = pa.items()[0]["id"]
    apply_analysis(pa, result(op(op="close", item_id=item_id, kind="waiting", title="Documents from Asha Rao")), m,
                   tz=IST, end_of_day=EOD)
    assert pa.item(item_id)["status"] == "closed" and pa.items() == []


def test_owner_hint_department_and_bad_ids(pa):
    m = msg(pa, "Please complete testing before Friday", channel="email", sender="lead@dev.example")
    out = apply_analysis(pa, result(
        op(kind="task", title="Complete testing", owner_hint="Priya", department="QA", due_text="before Friday",
           priority="high"),
        op(op="close", item_id=999, kind="task", title="Something unknown"),
    ), m, tz=IST, end_of_day=EOD)
    [row] = pa.items()
    assert row["owner_id"] == "u_priya" and row["department"] == "QA" and row["priority"] == "high"
    assert len(out.applied) == 1                                             # the bad close was ignored


def test_fix_moves_issue_to_retest(pa):
    issue = pa.create_item("owner", kind="qa_issue", title="Class scheduling fails for teachers", stage="new")
    m = msg(pa, "Scheduling bug is fixed, please check", sender="Dev", phone="911111111111")
    apply_analysis(pa, result(op(op="move_to_retest", item_id=issue, kind="qa_issue", title="Scheduling bug")), m,
                   tz=IST, end_of_day=EOD)
    row = pa.item(issue)
    assert row["status"] == "ready_for_retest" and row["stage"] == "retest" and row["verification"] == "pending"


def test_lead_and_quality_fields(pa):
    m = msg(pa, "Interested in admission for my son, what are the fees?")
    apply_analysis(pa, result(
        op(kind="lead", title="Admission enquiry from Asha Rao", lead_stage="new", priority="high",
           department="Admissions"),
        op(kind="quality", title="Class started late again", quality_category="Scheduling"),
    ), m, tz=IST, end_of_day=EOD)
    lead, quality = sorted(pa.items(), key=lambda r: r["kind"])
    assert lead["kind"] == "lead" and lead["stage"] == "new"
    assert quality["kind"] == "quality" and '"Scheduling"' in quality["data"]


def test_process_message_passes_open_items_as_context(pa):
    pa.create_item("owner", kind="waiting", title="Fee receipt from Asha Rao", status="waiting")
    llm = FakeLLM(result(importance="none", signals=["fyi"]))
    out = process_message(llm, pa, msg(pa, "Thanks!"), goals="- grow", tz=IST, end_of_day=EOD, team=["Robin"])
    assert out.applied == [] and "Fee receipt from Asha Rao" in llm.calls[0]
    assert "<body>\nThanks!\n</body>" in llm.calls[0]                       # message passed as data


def test_inbox_check_runs_pa_on_important_mail_and_whatsapp(tmp_path):
    from neuranova.config import load_settings
    from neuranova.jobs import Agent

    settings = load_settings(tmp_path / "x.toml", env={})
    store = Store(":memory:", "neuranova", "owner")
    brain = FakeBrain({"Quote": LEAD})
    brain.llm = FakeLLM(
        result(op(kind="lead", title="Quote request from Asha", lead_stage="new")),
        result(op(kind="waiting", title="Payment from Asha", waiting_on="Asha", due_text="tomorrow")),
    )
    agent = Agent(settings, store, brain, FakeNotifier(), mail=[FakeMail([email("Quote", "1", recent())])])
    cid = store.pa.contact_for(name="Asha", phone="919876543210")
    store.pa.add_message("whatsapp", "in", "wamid.1", "I'll pay the fee tomorrow", datetime.now(timezone.utc),
                         sender="919876543210", contact_id=cid)
    store.pa.add_message("whatsapp", "in", "wamid.2", "ok", datetime.now(timezone.utc), contact_id=cid)
    assert agent.check_inbox()["pa"] == 2
    kinds = sorted(r["kind"] for r in store.pa.items())
    assert kinds == ["lead", "waiting"]
    assert agent.check_inbox()["pa"] == 0                                     # nothing analyzed twice
