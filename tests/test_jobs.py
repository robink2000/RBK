from datetime import datetime, timedelta, timezone

from neuranova.jobs import Agent
from neuranova.models import EmailMessage, Task, Triage


class FakeMail:
    name = "gmail"

    def __init__(self, messages, replies=None):
        self.messages, self.replies = messages, replies or {}

    def fetch_inbox(self, since):
        return self.messages

    def latest_replies(self, since):
        return self.replies


class FakeBrain:
    def __init__(self, verdicts):
        self.verdicts = verdicts

    def triage(self, emails):
        return {e.id: self.verdicts[e.subject] for e in emails if e.subject in self.verdicts}

    def write_brief(self, facts):
        self.facts = facts
        return "brief"


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)


class FakeTodoist:
    def __init__(self, tasks):
        self.tasks = tasks

    def today_and_overdue(self):
        return self.tasks


LEAD = Triage("lead", "high", True, "Wants a quote", "Send pricing")
NEWS = Triage("newsletter", "low", False, "Weekly digest", "No action")


def email(subject, ext_id, received):
    return EmailMessage("gmail", ext_id, f"t-{ext_id}", "Asha <asha@x.com>", subject, "...", received)


def make_agent(settings, store, mail, brain, todoist=None):
    return Agent(settings, store, brain, FakeNotifier(), mail=[mail], todoist=todoist)


def test_check_inbox_triages_alerts_and_dedupes(settings, store):
    now = datetime.now(timezone.utc)
    mail = FakeMail([email("Quote", "1", now - timedelta(minutes=10)), email("Digest", "2", now)])
    agent = make_agent(settings, store, mail, FakeBrain({"Quote": LEAD, "Digest": NEWS}))

    assert agent.check_inbox() == {"new": 2, "triaged": 2, "replied": 0}
    assert len(agent.notifier.sent) == 1 and "Wants a quote" in agent.notifier.sent[0]
    assert agent.check_inbox()["new"] == 0          # same mail again is ignored
    assert len(agent.notifier.sent) == 1            # and not re-alerted
    [waiting] = store.awaiting_reply()
    assert waiting["reply_deadline"] is not None    # lead is held to the 4h promise


def test_sla_warns_then_breaches_once_and_reply_clears(settings, store):
    old = datetime.now(timezone.utc) - timedelta(days=3)
    mail = FakeMail([email("Quote", "1", old)])
    agent = make_agent(settings, store, mail, FakeBrain({"Quote": LEAD}))
    agent.check_inbox()

    assert agent.check_sla() == {"warned": 0, "breached": 1}
    assert agent.check_sla() == {"warned": 0, "breached": 0}   # no repeat alert
    assert any("overdue" in m for m in agent.notifier.sent)

    mail.replies = {"t-1": datetime.now(timezone.utc)}
    agent.check_inbox()
    assert store.awaiting_reply() == []
    assert store.response_stats(old - timedelta(days=1))["late"] == 1


def test_task_reminder_sent_once(settings, store):
    soon = datetime.now(timezone.utc) + timedelta(minutes=10)
    later = datetime.now(timezone.utc) + timedelta(hours=5)
    todo = FakeTodoist([Task("1", "Call investor", 4, soon.date().isoformat(), soon),
                        Task("2", "Later thing", 1, later.date().isoformat(), later)])
    agent = make_agent(settings, store, FakeMail([]), FakeBrain({}), todoist=todo)
    assert agent.task_reminders() == 1
    assert agent.task_reminders() == 0
    assert "Call investor" in agent.notifier.sent[0] and "P1" in agent.notifier.sent[0]


def test_morning_brief_facts(settings, store):
    now = datetime.now(timezone.utc)
    mail = FakeMail([email("Quote", "1", now - timedelta(hours=1)), email("Digest", "2", now)])
    brain = FakeBrain({"Quote": LEAD, "Digest": NEWS})
    agent = make_agent(settings, store, mail, brain, todoist=FakeTodoist([]))
    assert agent.morning_brief() == "brief"
    facts = brain.facts
    assert facts["leads_new"] == 1
    assert facts["waiting_for_your_reply"][0]["from"] == "Asha"
    assert [e["subject"] for e in facts["important_new_email"]] == ["Quote"]
    assert agent.notifier.sent[-1] == "brief"
