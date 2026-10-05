"""The agent's recurring jobs. Each one is safe to run repeatedly (idempotent)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .brain import Brain, EmailForTriage
from .config import Settings
from .connectors import MailConnector
from .connectors.gmail import sender_name
from .connectors.todoist import TodoistConnector, localize
from .db import Store, row_dt
from .notify import Notifier
from .sla import reply_deadline

log = logging.getLogger(__name__)

FIRST_RUN_LOOKBACK = timedelta(days=2)
REPLY_LOOKBACK = timedelta(days=14)
SLA_NONE, SLA_WARNED, SLA_BREACHED = 0, 1, 2


@dataclass
class Agent:
    settings: Settings
    store: Store
    brain: Brain
    notifier: Notifier
    mail: list[MailConnector] = field(default_factory=list)
    todoist: TodoistConnector | None = None

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _fmt(self, dt: datetime) -> str:
        return dt.astimezone(self.settings.tz).strftime("%a %H:%M")

    def _held_to_sla(self, category: str, priority: str, needs_reply: bool) -> bool:
        return needs_reply and (category in self.settings.sla_categories or priority == "high")

    # --- inbox ----------------------------------------------------------------

    def check_inbox(self) -> dict[str, int]:
        now = self._now()
        stats = {"new": 0, "triaged": 0, "replied": 0}
        for conn in self.mail:
            key = f"last_check:{conn.name}"
            since = row_dt(self.store.get(key)) or now - FIRST_RUN_LOOKBACK
            try:
                messages = conn.fetch_inbox(since - timedelta(minutes=5))  # small overlap; inserts dedupe
                for msg in messages:
                    stats["new"] += self.store.add_email(msg)
                for thread_id, at in conn.latest_replies(now - REPLY_LOOKBACK).items():
                    stats["replied"] += self.store.mark_replied(conn.name, thread_id, at)
                self.store.put(key, now.isoformat())
            except Exception:
                log.exception("Mail check failed for %s", conn.name)
                self.store.log("error", job="check_inbox", source=conn.name)

        stats["triaged"] = self.triage_pending()
        if self.settings.instant_high_priority:
            self.alert_high_priority()
        self.store.log("check_inbox", **stats)
        return stats

    def triage_pending(self) -> int:
        done = 0
        while rows := self.store.untriaged(limit=20):
            batch = [EmailForTriage(r["id"], r["sender"], r["subject"], r["snippet"]) for r in rows]
            results = self.brain.triage(batch)
            for r in rows:
                t = results.get(r["id"])
                if t is None:
                    continue
                deadline = None
                if self._held_to_sla(t.category, t.priority, t.needs_reply):
                    deadline = reply_deadline(row_dt(r["received_at"]), self.settings.sla_hours,
                                              self.settings.working_hours, self.settings.tz)
                self.store.save_triage(r["id"], t, deadline)
                done += 1
            if not results:
                break  # nothing usable came back; these stay untriaged and are retried next run
        return done

    def alert_high_priority(self) -> None:
        for r in self.store.unalerted_high_priority():
            received = row_dt(r["received_at"])
            if self._now() - received < timedelta(hours=12):  # don't replay old mail on first run
                lines = [f"🔴 High-priority email ({r['source']})",
                         f"From: {sender_name(r['sender'])}",
                         f"Subject: {r['subject']}",
                         f"What: {r['summary']}",
                         f"Do: {r['suggested_action']}"]
                if r["reply_deadline"]:
                    lines.append(f"Reply by: {self._fmt(row_dt(r['reply_deadline']))}")
                self.notifier.send("\n".join(lines))
                self.store.log("alert_high_priority", email_id=r["id"])
            self.store.mark_alerted(r["id"])

    # --- response-time promise ---------------------------------------------

    def check_sla(self) -> dict[str, int]:
        now = self._now()
        warn = timedelta(minutes=self.settings.sla_warn_minutes)
        sent = {"warned": 0, "breached": 0}
        for r in self.store.awaiting_reply():
            deadline = row_dt(r["reply_deadline"])
            if deadline is None:
                continue
            who = sender_name(r["sender"])
            if now >= deadline and r["sla_stage"] < SLA_BREACHED:
                late = now - deadline
                self.notifier.send(
                    f"⚠️ Reply overdue by {int(late.total_seconds() // 3600)}h {int(late.total_seconds() % 3600 // 60)}m\n"
                    f"{who}: {r['subject']}\n{r['summary']}\nDo: {r['suggested_action']}"
                )
                self.store.set_sla_stage(r["id"], SLA_BREACHED)
                sent["breached"] += 1
            elif deadline - warn <= now < deadline and r["sla_stage"] < SLA_WARNED:
                mins = int((deadline - now).total_seconds() // 60)
                self.notifier.send(
                    f"⏳ {mins} min left to reply ({self.settings.sla_hours:g}h promise)\n{who}: {r['subject']}\n"
                    f"{r['summary']}\nDo: {r['suggested_action']}"
                )
                self.store.set_sla_stage(r["id"], SLA_WARNED)
                sent["warned"] += 1
        if any(sent.values()):
            self.store.log("check_sla", **sent)
        return sent

    # --- tasks ------------------------------------------------------------------

    def task_reminders(self) -> int:
        if not self.todoist:
            return 0
        now = self._now()
        horizon = now + timedelta(minutes=self.settings.task_reminder_lead_minutes)
        count = 0
        for task in self.todoist.today_and_overdue():
            due = localize(task, self.settings.tz)
            if due is None or not (now - timedelta(minutes=5) <= due <= horizon):
                continue
            if self.store.reminder_sent(task.id, due.isoformat()):
                continue
            self.notifier.send(f"⏰ {task.content}\nDue {self._fmt(due)} · {task.label}\n{task.url}")
            count += 1
        if count:
            self.store.log("task_reminders", sent=count)
        return count

    # --- morning brief ---------------------------------------------------------

    def gather_brief_facts(self) -> dict:
        now = self._now()
        since = row_dt(self.store.get("last_brief")) or now - timedelta(days=1)
        new = self.store.received_since(since)
        by_category: dict[str, int] = {}
        for r in new:
            by_category[r["category"]] = by_category.get(r["category"], 0) + 1

        waiting = []
        for r in self.store.awaiting_reply():
            deadline = row_dt(r["reply_deadline"])
            waiting.append({
                "from": sender_name(r["sender"]), "subject": r["subject"], "summary": r["summary"],
                "action": r["suggested_action"], "category": r["category"], "priority": r["priority"],
                "reply_by": self._fmt(deadline) if deadline else None,
                "overdue": bool(deadline and now > deadline),
            })

        important_new = [
            {"from": sender_name(r["sender"]), "subject": r["subject"], "summary": r["summary"],
             "category": r["category"], "priority": r["priority"]}
            for r in new if r["priority"] in ("high", "medium") and r["category"] not in ("newsletter", "spam")
        ][:15]

        tasks = []
        if self.todoist:
            try:
                for t in sorted(self.todoist.today_and_overdue(), key=lambda t: -t.priority)[:20]:
                    due = localize(t, self.settings.tz)
                    tasks.append({"task": t.content, "priority": t.label, "due": t.due_date,
                                  "time": due.strftime("%H:%M") if due else None,
                                  "overdue": bool(t.due_date and t.due_date < now.astimezone(self.settings.tz).date().isoformat())})
            except Exception:
                log.exception("Could not load Todoist tasks for the brief")

        return {
            "date": now.astimezone(self.settings.tz).strftime("%A %d %B %Y"),
            "new_email_by_category": by_category,
            "leads_new": by_category.get("lead", 0),
            "important_new_email": important_new,
            "waiting_for_your_reply": waiting[:15],
            "response_promise": f"reply to clients/leads within {self.settings.sla_hours:g} business hours",
            "response_record_last_7_days": self.store.response_stats(now - timedelta(days=7)),
            "tasks_today_and_overdue": tasks,
        }

    def morning_brief(self) -> str:
        self.check_inbox()
        facts = self.gather_brief_facts()
        text = self.brain.write_brief(facts)
        self.notifier.send(text)
        self.store.put("last_brief", self._now().isoformat())
        self.store.log("morning_brief", chars=len(text))
        return text
