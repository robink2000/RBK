"""`neuranova demo`: the full console on your own computer with sample data.

No accounts, API keys or internet needed (except the web fonts). Uses its own database
(data/demo.db), so it never touches real data. Sending a draft or finishing a task works,
but the "email" only goes to this demo's memory.
"""

from __future__ import annotations

import random
import secrets
import webbrowser
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import load_settings
from .db import Store
from .jobs import Agent
from .models import Draft, EmailMessage, Task, Triage
from .team import accept_invite, create_invite, ensure_owner

DEMO_EMAIL = "you@neuranova.demo"
DEMO_PASSWORD = "neuranova-demo"

PEOPLE = ["Asha Rao <asha@acme.example>", "Vikram Nair <vikram@globex.example>",
          "Meera Iyer <meera@initech.example>", "Tom Becker <tom@umbrella.example>"]
LEADS = ["Daniel Okafor <daniel@brightpath.example>", "Sara Lindqvist <sara@nordlight.example>",
         "Kabir Mehta <kabir@tealstone.example>", "Lucia Romero <lucia@solaria.example>",
         "Hana Sato <hana@kumo.example>", "Omar Haddad <omar@cedarlabs.example>"]


class QuietNotifier:
    """The demo shows everything in the console, so WhatsApp messages go nowhere."""

    def send(self, text, teaser=None):
        pass


class DemoMail:
    name = "gmail"

    def __init__(self, messages):
        self.messages, self.replies, self.sent = messages, {}, []

    def fetch_inbox(self, since):
        return self.messages

    def latest_replies(self, since):
        return self.replies

    def fetch_body(self, external_id):
        return "Hi, could you share pricing and timelines for a 3-month engagement? Thanks!"

    def send_reply(self, external_id, body):
        self.sent.append((external_id, body))  # demo only: nothing leaves this computer
        return f"demo-{external_id}"


class DemoBrain:
    """Stands in for Claude so the demo runs offline."""

    def __init__(self, verdicts):
        self.verdicts = verdicts

    def triage(self, emails):
        return {e.id: self.verdicts[e.subject] for e in emails if e.subject in self.verdicts}

    def draft_reply(self, sender, subject, body):
        first = sender.split()[0]
        return Draft(f"Hi {first},\n\nThanks for reaching out. For a 3-month engagement the fee would be "
                     f"[price for 3 months], and we could start within two weeks.\n\nWould a short call on "
                     f"Tuesday work to go through the details?\n\nBest regards,\n[Your name]\nNeuraNova",
                     ["What price should we quote for 3 months?"])

    def revise_draft(self, sender, subject, body, current, instruction):
        return Draft(current, [])

    def write_brief(self, facts):
        return "(The demo doesn't call Claude, so there's no written brief.)"

    def write_weekly(self, facts):
        return self.write_brief(facts)


class DemoTodoist:
    def __init__(self, tasks):
        self.tasks = tasks

    def today_and_overdue(self):
        return list(self.tasks)

    def filter(self, query):
        return list(self.tasks)

    def add_task(self, content, description="", due_string="", priority=1):
        task = Task(str(100 + len(self.tasks)), content, priority, None, None, "https://todoist.com")
        self.tasks.append(task)
        return task

    def close_task(self, task_id):
        self.tasks = [t for t in self.tasks if t.id != task_id]


def build_demo(db_path: Path, config_path: str | None = None, fresh: bool = True):
    if fresh and db_path.exists():
        db_path.unlink()
    secret = secrets.token_urlsafe(48)
    env = {"DASHBOARD_PASSWORD": DEMO_PASSWORD, "DASHBOARD_SECRET": secret, "DASHBOARD_INSECURE_COOKIE": "1",
           "OWNER_EMAIL": DEMO_EMAIL, "OWNER_NAME": "You", "NEURANOVA_DB": str(db_path)}
    settings = load_settings(config_path, env=env)
    settings = replace(settings, max_drafts_per_run=3, draft_lookback_days=30, instant_high_priority=False)
    store = Store(db_path, settings.workspace_id, settings.owner_id)
    ensure_owner(store, settings)

    rng = random.Random(7)
    now = datetime.now(timezone.utc)
    topics = ["Website redesign", "Pricing for 3 months", "Mobile app quote", "Follow-up on proposal",
              "Invoice question", "Partnership idea", "Logo revisions", "Kick-off meeting"]
    messages, verdicts = [], {}
    for i in range(36):
        received = now - timedelta(days=rng.randint(0, 55), hours=rng.randint(0, 8))
        subject = f"{topics[i % len(topics)]} #{i}"
        sender = rng.choice(PEOPLE) if i % 3 else LEADS[(i // 3) % len(LEADS)]
        messages.append(EmailMessage("gmail", str(i), f"t-{i}", sender, subject,
                                     "Could you share pricing and timelines?", received,
                                     link="https://mail.google.com"))
        verdicts[subject] = Triage("lead" if i % 3 == 0 else "client", "high" if i % 4 == 0 else "medium", True,
                                   f"Asks about {topics[i % len(topics)].lower()}", "Reply with details")
    mail = DemoMail(messages)
    todoist = DemoTodoist([
        Task("1", "Send proposal to Acme", 4, now.date().isoformat(), now + timedelta(hours=3), "https://todoist.com"),
        Task("2", "Pay hosting invoice", 3, (now - timedelta(days=2)).date().isoformat(), None, "https://todoist.com"),
        Task("3", "Review Globex feedback", 1, now.date().isoformat(), None, "https://todoist.com"),
    ])
    agent = Agent(settings, store, DemoBrain(verdicts), QuietNotifier(), mail=[mail], todoist=todoist,
                  notifier_factory=lambda number: QuietNotifier())
    agent.check_inbox()
    mail.replies = {m.thread_id: m.received_at + timedelta(hours=rng.choice([1, 2, 3, 30, 50]))
                    for i, m in enumerate(messages) if i % 5 and m.received_at < now - timedelta(hours=10)}
    agent.check_inbox()

    today = datetime.now(settings.tz).date()
    for days_ago, kind, client, value in [(0, "deal_won", "Acme", 150000), (1, "proposal_sent", "Globex", None),
                                          (2, "meeting", "Initech", None), (3, "delivery_on_time", "Acme", None),
                                          (4, "feedback_positive", "Acme", None), (5, "rework", "Umbrella", None),
                                          (9, "deal_won", "Initech", 80000), (12, "delivery_late", "Globex", None)]:
        store.add_event((today - timedelta(days=days_ago)).isoformat(), kind, client, value, "", source="demo")

    owner = store.user(settings.owner_id)
    priya = store.user(accept_invite(store, create_invite(store, owner, "priya@neuranova.demo", "Priya (sample)",
                                                          "member"), "priya-demo-pass"))
    agent.assign_team_task(owner, priya, "Send banner drafts to Acme", now + timedelta(days=1, hours=2))
    agent.assign_team_task(owner, owner, "Prepare Q4 pitch deck", now + timedelta(days=2))
    seed_pa(store, settings, owner, priya, now)
    return settings, store, agent


def seed_pa(store, settings, owner, priya, now) -> None:
    """Sample PA data: leads, promises, application issues, quality concerns, WhatsApp, approvals."""
    from .pa import prefs

    pa = store.pa
    me, p = owner["id"], priya["id"]
    sharma = pa.contact_for("Mrs. Sharma (sample)", phone="919800000001", role="parent")
    kumar = pa.contact_for("Mr. Kumar (sample)", phone="919800000002", role="parent")
    rahul = pa.contact_for("Rahul - developer (sample)", phone="919800000003", role="developer")
    for title, stage, value, days, contact, prio in [
        ("Sharma family - Grade 6 admission", "demo_pending", 45000, 1, sharma, "high"),
        ("Kumar - two children, Grade 3 and 7", "payment_pending", 90000, 2, kumar, "high"),
        ("Greenfield School - teacher training", "quoted", 250000, 8, None, "medium"),
        ("Online coding course enquiry (Instagram)", "contacted", 12000, 6, None, "medium"),
        ("Iyer family - summer camp", "converted", 18000, 3, None, "medium"),
        ("Bose - Grade 9 maths", "lost", 30000, 10, None, "low"),
    ]:
        item = pa.create_item(me, kind="lead", title=title, stage=stage, value=value, contact_id=contact,
                              priority=prio, owner_id=p if stage != "quoted" else me, department="Admissions",
                              source="whatsapp" if contact else "manual",
                              status="closed" if stage in ("converted", "lost") else "open",
                              follow_up_at=now + timedelta(hours=3) if stage == "demo_pending" else None)
        pa.conn.execute("UPDATE items SET updated_at = ?, created_at = ? WHERE id = ?",
                        ((now - timedelta(days=days)).isoformat(), (now - timedelta(days=days + 2)).isoformat(), item))
        if stage == "lost":
            pa.update_item(item, me, data={"lost_reason": "Fees too high"})
    pa.create_item(me, kind="waiting", title="Rahul to share the login fix build", waiting_on="Rahul (sample)",
                   status="waiting", due_at=now - timedelta(hours=5), contact_id=rahul, department="Application",
                   waiting_since=now - timedelta(days=2), source="whatsapp")
    pa.create_item(me, kind="follow_up", title="Send fee structure to Mr. Kumar", owner_id=me, priority="high",
                   due_at=now + timedelta(hours=2), contact_id=kumar, department="Admissions")
    pa.create_item(me, kind="decision", title="Approve new mentor salary bands", priority="high",
                   department="Management", due_at=now + timedelta(days=1))
    pa.create_item(me, kind="task", title="Publish November class timetable", owner_id=p, priority="medium",
                   department="Academics", due_at=now - timedelta(days=1))
    for title, stage, envname in [("Student dashboard: 'Join class' button does nothing", "fix_required", "development"),
                                  ("Mentor login slow on Production (8 s)", "ready_for_test", "production"),
                                  ("Teacher attendance export shows wrong dates", "new", "development")]:
        pa.create_item("QA", kind="qa_issue", title=title, stage=stage, department="Application", priority="high",
                       status="ready_for_retest" if stage == "ready_for_test" else "open", source="qa",
                       data={"environment": envname, "occurrences": 2})
    for days, title in [(1, "Class started 20 minutes late (Grade 6)"), (4, "Teacher joined late for revision class"),
                        (9, "Grade 8 class moved without telling parents")]:
        i = pa.create_item(me, kind="quality", title=title, department="Academics", data={"category": "Scheduling"})
        pa.conn.execute("UPDATE items SET created_at = ? WHERE id = ?", ((now - timedelta(days=days)).isoformat(), i))
    pa.conn.commit()
    pa.add_message("whatsapp", "in", "demo-1", "Hi, can we do the demo class tomorrow at 5pm? My daughter is free then.",
                   now - timedelta(hours=3), sender="919800000001", contact_id=sharma)
    pa.add_message("whatsapp", "in", "demo-2", "Payment link not working, please check", now - timedelta(hours=26),
                   sender="919800000002", contact_id=kumar)
    pa.add_outbox("whatsapp", "919800000002", "Hello Mr. Kumar, sorry about the payment link. Here is a fresh one: "
                  "[link]. The fee for both children is ₹90,000 for the year. Happy to help with anything else.",
                  me, recipient_name="Mr. Kumar (sample)", reason="Reply to: payment link not working")
    run = pa.start_qa_run("development")
    pa.finish_qa_run(run, "failed", "5 of 6 checks passed", [
        {"environment": "development", "role": r, "workflow": "Sign in and open home", "ok": r != "Student",
         "error": "" if r != "Student" else "Expected text 'Join class' not found", "duration_ms": 2100}
        for r in ("Super Admin", "Mentor", "Teacher", "Student", "Coordinator", "IT Support")])
    prefs.save(store, {"setup_done": True}, "demo")


def run_demo(port: int = 8080, open_browser: bool = True, config_path: str | None = None) -> None:
    import uvicorn

    from .server import create_app

    settings, store, agent = build_demo(Path("data/demo.db"), config_path)
    app = create_app(settings, lambda: agent, store=store)
    url = f"http://localhost:{port}"
    print(f"""
  NeuraNova console demo is running at  {url}

    Email:     {DEMO_EMAIL}
    Password:  {DEMO_PASSWORD}

  Sample data only (data/demo.db). Press Ctrl+C to stop.
""", flush=True)
    if open_browser:
        try:
            webbrowser.open(f"{url}/login")
        except Exception:
            pass
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
