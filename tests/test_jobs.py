from datetime import datetime, timedelta, timezone

from neuranova.commands import handle
from neuranova.jobs import Agent
from neuranova.models import Draft, EmailMessage, Task, Triage


class FakeMail:
    name = "gmail"

    def __init__(self, messages, replies=None, fail_send=False):
        self.messages, self.replies = messages, replies or {}
        self.sent, self.fail_send = [], fail_send

    def fetch_inbox(self, since):
        return self.messages

    def latest_replies(self, since):
        return self.replies

    def fetch_body(self, external_id):
        return f"full body of {external_id}"

    def send_reply(self, external_id, body):
        if self.fail_send:
            raise RuntimeError("smtp down")
        self.sent.append((external_id, body))
        return "sent-1"


class FakeBrain:
    def __init__(self, verdicts, draft="Hi Asha,\nThanks!\nBest"):
        self.verdicts, self.draft = verdicts, draft
        self.revisions = []

    def triage(self, emails):
        return {e.id: self.verdicts[e.subject] for e in emails if e.subject in self.verdicts}

    def draft_reply(self, sender, subject, body):
        return Draft(self.draft, [])

    def revise_draft(self, sender, subject, body, current, instruction):
        self.revisions.append(instruction)
        return Draft(f"{current} (revised: {instruction})", [])

    def write_brief(self, facts):
        self.facts = facts
        return "brief"


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, text, teaser=None):
        self.sent.append(text)


class FakeTodoist:
    def __init__(self, tasks=()):
        self.tasks, self.added = list(tasks), []

    def today_and_overdue(self):
        return self.tasks

    def add_task(self, content, description="", due_string="", priority=1):
        self.added.append((content, description, due_string, priority))
        return Task(str(len(self.added)), content, priority, None, None)


LEAD = Triage("lead", "high", True, "Wants a quote", "Send pricing",
              create_task=True, task_title="Prepare quote for Asha", task_due="friday")
NEWS = Triage("newsletter", "low", False, "Weekly digest", "No action")


def email(subject, ext_id, received):
    return EmailMessage("gmail", ext_id, f"t-{ext_id}", "Asha <asha@x.com>", subject, "...", received,
                        link=f"https://mail/{ext_id}")


def make_agent(settings, store, mail, brain, todoist=None):
    return Agent(settings, store, brain, FakeNotifier(), mail=[mail], todoist=todoist)


def recent(minutes=10):
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


def test_check_inbox_triages_alerts_and_dedupes(settings, store):
    mail = FakeMail([email("Quote", "1", recent()), email("Digest", "2", recent(0))])
    agent = make_agent(settings, store, mail, FakeBrain({"Quote": LEAD, "Digest": NEWS}), FakeTodoist())

    assert agent.check_inbox() == {"new": 2, "triaged": 2, "replied": 0, "pa": 0, "drafts": 1}
    assert "Wants a quote" in agent.notifier.sent[0]           # instant high-priority alert
    assert "Draft #1" in agent.notifier.sent[1]                 # then the draft for approval
    assert agent.check_inbox() == {"new": 0, "triaged": 0, "replied": 0, "pa": 0, "drafts": 0}
    assert len(agent.notifier.sent) == 2                        # nothing repeated
    [waiting] = store.awaiting_reply()
    assert waiting["reply_deadline"] is not None


def test_send_draft_flow(settings, store):
    mail = FakeMail([email("Quote", "1", recent())])
    agent = make_agent(settings, store, mail, FakeBrain({"Quote": LEAD}))
    agent.check_inbox()

    assert "✅ Sent" in handle(agent, "send 1")
    assert mail.sent == [("1", "Hi Asha,\nThanks!\nBest")]
    assert store.awaiting_reply() == []                         # reply clears the deadline
    assert "already sent" in handle(agent, "send 1")            # never sent twice
    assert len(mail.sent) == 1


def test_draft_with_blanks_is_not_sent(settings, store):
    mail = FakeMail([email("Quote", "1", recent())])
    agent = make_agent(settings, store, mail, FakeBrain({"Quote": LEAD}, draft="Price is [price]."))
    agent.check_inbox()
    assert "still has blanks: [price]" in handle(agent, "send 1")
    assert mail.sent == []
    assert "Draft #1" in handle(agent, "edit 1 Hi Asha,\nPrice is $500.\nBest")
    assert "✅ Sent" in handle(agent, "send #1")
    assert mail.sent == [("1", "Hi Asha,\nPrice is $500.\nBest")]


def test_redo_skip_and_failed_send(settings, store):
    mail = FakeMail([email("Quote", "1", recent()), email("Other", "2", recent())], fail_send=True)
    brain = FakeBrain({"Quote": LEAD, "Other": LEAD})
    agent = make_agent(settings, store, mail, brain)
    agent.check_inbox()

    assert "revised: shorter please" in handle(agent, "redo 1 shorter please")
    assert "failed" in handle(agent, "send 1")
    assert store.draft(1)["status"] == "pending"                # still there to retry
    assert "Skipped" in handle(agent, "skip 2")
    assert [d["id"] for d in store.pending_drafts()] == [1]
    assert "Draft #1" in handle(agent, "drafts")
    assert "Which draft?" in handle(agent, "send")
    assert "drafts - show" in handle(agent, "hello")


def test_replying_yourself_closes_the_draft(settings, store):
    mail = FakeMail([email("Quote", "1", recent())])
    agent = make_agent(settings, store, mail, FakeBrain({"Quote": LEAD}))
    agent.check_inbox()
    mail.replies = {"t-1": datetime.now(timezone.utc)}
    agent.check_inbox()
    assert store.pending_drafts() == []
    assert "already skipped" in handle(agent, "send 1")


def test_sla_warns_then_breaches_once_and_reply_clears(settings, store):
    old = datetime.now(timezone.utc) - timedelta(days=3)
    mail = FakeMail([email("Quote", "1", old)])
    agent = make_agent(settings, store, mail, FakeBrain({"Quote": LEAD}))
    agent.check_inbox()

    assert agent.check_sla() == {"warned": 0, "breached": 1}
    assert agent.check_sla() == {"warned": 0, "breached": 0}
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


def test_morning_brief_is_a_saved_report(settings, store):
    mail = FakeMail([email("Quote", "1", recent(60)), email("Digest", "2", recent(0))])
    brain = FakeBrain({"Quote": LEAD, "Digest": NEWS})
    agent = make_agent(settings, store, mail, brain, todoist=FakeTodoist())
    text = agent.morning_brief()
    assert "Morning Brief" in text and "waiting for your reply" in text      # plain version without AI
    assert agent.notifier.sent[-1] == text
    [report] = store.pa.reports("morning")
    assert report["text"] == text
