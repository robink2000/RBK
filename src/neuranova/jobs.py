"""The agent's recurring jobs. Each one is safe to run repeatedly (idempotent)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from .brain import Brain, EmailForTriage
from .config import Settings
from .connectors import MailConnector
from .connectors.gmail import sender_name
from .connectors.todoist import TodoistConnector, localize
from .db import Store, row_dt
from .notify import Notifier
from .progress import compute as compute_progress, team_stats, weekly_series
from .sla import reply_deadline
from .team import TeamError, can_change, format_task

log = logging.getLogger(__name__)

FIRST_RUN_LOOKBACK = timedelta(days=2)
REPLY_LOOKBACK = timedelta(days=14)
SLA_NONE, SLA_WARNED, SLA_BREACHED = 0, 1, 2
TODOIST_PRIORITY = {"high": 4, "medium": 3, "low": 1}  # 4 = P1
PLACEHOLDER = re.compile(r"\[[^\]\n]{1,80}\]")


@dataclass
class Agent:
    settings: Settings
    store: Store
    brain: Brain
    notifier: Notifier
    mail: list[MailConnector] = field(default_factory=list)
    todoist: TodoistConnector | None = None
    notifier_factory: Callable[[str], Notifier] | None = None  # WhatsApp number -> notifier for that person

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _fmt(self, dt: datetime) -> str:
        return dt.astimezone(self.settings.tz).strftime("%a %H:%M")

    def connector(self, source: str) -> MailConnector | None:
        return next((c for c in self.mail if c.name == source), None)

    def _fmt_deadline(self, row) -> str:
        return self._fmt(row_dt(row["reply_deadline"])) if row["reply_deadline"] else "no deadline"

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
        self.store.close_drafts_for_replied()
        if self.settings.instant_high_priority:
            self.alert_high_priority()
        stats["pa"] = self.analyze_communications()
        if self.settings.drafts_enabled:
            stats["drafts"] = self.draft_replies()
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

    # --- PA: understand communication and keep work items current ------------------------

    @property
    def pa(self):
        return self.store.pa

    def _find_owner(self, hint: str):
        from .team import find_member
        return find_member(self.store, hint)

    def analyze_communications(self, limit: int = 10) -> int:
        """Run the PA's analysis on new important emails and WhatsApp messages from contacts."""
        from .brain import goals_text
        from .pa.comms import Incoming, process_message

        llm = getattr(self.brain, "llm", None)
        if llm is None or not hasattr(llm, "json"):
            return 0
        team = [u["name"] for u in self.store.users()]
        goals = goals_text(self.settings.goals)
        done = 0
        for r in self.store.emails_for_pa(limit):
            conn = self.connector(r["source"])
            body = r["snippet"]
            try:
                if conn is not None:
                    body = conn.fetch_body(r["external_id"]) or body
            except Exception:
                log.warning("Could not fetch the full email %s; using the preview", r["id"])
            from email.utils import parseaddr
            name, addr = parseaddr(r["sender"])
            contact_id = self.pa.contact_for(name=name, email=addr)
            msg = Incoming("email", str(r["id"]), r["sender"], r["subject"], body, row_dt(r["received_at"]),
                           contact_id=contact_id, link=r["link"])
            try:
                out = process_message(llm, self.pa, msg, goals=goals, tz=self.settings.tz,
                                      end_of_day=self.settings.working_hours.end, team=team,
                                      find_owner=self._find_owner)
            except Exception:
                log.exception("PA analysis failed for email %s", r["id"])
                continue
            self.store.mark_email_pa(r["id"])
            self.store.log("pa_analyzed", channel="email", ref=r["id"], changes=out.applied)
            done += 1
        for m in self.pa.unanalyzed_messages(limit):
            text = (m["body"] or "").strip()
            if len(text) < 4 or not any(ch.isalnum() for ch in text):
                self.pa.mark_analyzed(m["id"], text, "none")  # "ok", emoji: nothing to track
                continue
            msg = Incoming(m["channel"], str(m["id"]), m["contact_name"] or m["sender"], m["subject"], text,
                           row_dt(m["at"]), contact_id=m["contact_id"])
            try:
                out = process_message(llm, self.pa, msg, goals=goals, tz=self.settings.tz,
                                      end_of_day=self.settings.working_hours.end, team=team,
                                      find_owner=self._find_owner)
            except Exception:
                log.exception("PA analysis failed for message %s", m["id"])
                continue
            self.pa.mark_analyzed(m["id"], out.summary, out.importance)
            self.store.log("pa_analyzed", channel=m["channel"], ref=m["id"], changes=out.applied)
            done += 1
        return done

    def proactive(self) -> dict:
        """Tell the founder what needs attention (digest, no repeats, no spam)."""
        from .pa import proactive
        return proactive.run(self.store, self.settings, self.notifier.send)

    def run_qa(self, environment: str) -> dict:
        """Run the application checks for one environment, record issues, alert on Production problems."""
        from pathlib import Path

        from .integrations import qa_config
        from .pa import qa

        cfg = qa_config(self.settings, self.store)
        base = cfg.get(environment)
        if not base:
            return {"skipped": f"No {qa.ENVIRONMENTS[environment]} address set"}
        run_id = self.pa.start_qa_run(environment)
        evidence = Path(self.settings.db_path).parent / "qa" / f"run-{run_id}" if str(self.settings.db_path) != ":memory:" \
            else Path("data/qa") / f"run-{run_id}"
        try:
            results = qa.run_environment(environment, base, cfg["accounts"].get(environment, {}),
                                         qa.parse_workflows(cfg["workflows"]), evidence,
                                         login_path=cfg["login_path"], allow_prod_login=cfg["allow_prod_login"])
        except Exception as exc:
            log.exception("QA run failed to start")
            self.pa.finish_qa_run(run_id, "error", str(exc)[:300], [])
            return {"error": str(exc)}
        counts = qa.record(self.pa, results)
        failed = [r for r in results if not r.ok]
        self.pa.finish_qa_run(run_id, "failed" if failed else "passed", qa.summary_text(results, counts),
                              qa.results_json(results))
        self.store.log("qa_run", environment=environment, **counts)
        if environment == "production" and (counts["new"] or counts["regressions"]):
            lines = [f"🚨 NeuraNova Production: {len(failed)} check(s) failing"]
            lines += [f"- {r.role} · {r.workflow}: {r.error[:120]}" for r in failed[:5]]
            self.notifier.send("\n".join(lines), teaser=f"NeuraNova Production: {len(failed)} check(s) failing.")
        return {"run_id": run_id, "passed": len(results) - len(failed), "failed": len(failed), **counts}

    def briefing(self, meetings: list | None = None, user_name: str = "") -> dict:
        from .pa import briefing
        if meetings is None:
            meetings = self.meetings()["today"]
        return briefing.build(self.store, self.settings, meetings=meetings, user_name=user_name)

    # --- email -> Todoist ----------------------------------------------------

    def create_tasks(self) -> int:
        created = 0
        for r in self.store.tasks_to_create():
            description = (f"From: {r['sender']}\nSubject: {r['subject']}\n{r['summary']}"
                           + (f"\n\nOpen email: {r['link']}" if r["link"] else ""))
            try:
                task = self.todoist.add_task(
                    r["task_title"], description=description, due_string=r["task_due"],
                    priority=TODOIST_PRIORITY.get(r["priority"], 1),
                )
            except Exception:
                log.exception("Could not create Todoist task for email %s", r["id"])
                continue
            self.store.set_task_id(r["id"], task.id)
            self.store.log("task_created", email_id=r["id"], task_id=task.id, title=r["task_title"])
            created += 1
        return created

    # --- reply drafts ---------------------------------------------------------

    def draft_replies(self) -> int:
        made = 0
        since = self._now() - timedelta(days=self.settings.draft_lookback_days)
        for r in self.store.needing_draft(since, self.settings.max_drafts_per_run):
            conn = self.connector(r["source"])
            if conn is None:
                continue
            try:
                body = conn.fetch_body(r["external_id"])
                draft = self.brain.draft_reply(r["sender"], r["subject"], body)
            except Exception:
                log.exception("Could not draft a reply for email %s", r["id"])
                continue
            draft_id = self.store.add_draft(r["id"], draft.reply, draft.needs_input)
            self.store.log("draft_created", email_id=r["id"], draft_id=draft_id)
            self.notifier.send(self.format_draft(self.store.draft(draft_id)),
                               teaser=f"Draft #{draft_id} ready for {sender_name(r['sender'])} - "
                                      f"{r['subject']}. Reply 'drafts' to review it.")
            made += 1
        return made

    def format_draft(self, d) -> str:
        email = self.store.email(d["email_id"])
        lines = [f"✉️ Draft #{d['id']} → {sender_name(d['sender'])} ({email['category']})",
                 f"Re: {d['subject']}"]
        if email["reply_deadline"]:
            lines.append(f"Reply by {self._fmt(row_dt(email['reply_deadline']))}")
        lines += ["", d["body"], ""]
        needs = json.loads(d["needs_input"] or "[]")
        if needs:
            lines += ["❓ Needs you:"] + [f"- {q}" for q in needs] + [""]
        n = d["id"]
        lines.append(f"Reply: send {n} · edit {n} <your text> · redo {n} <what to change> · skip {n}")
        return "\n".join(lines)

    def send_draft(self, draft_id: int) -> str:
        d = self.store.draft(draft_id)
        if d is None:
            return f"No draft #{draft_id}."
        if d["status"] != "pending":
            return f"Draft #{draft_id} is already {d['status']}."
        if gaps := PLACEHOLDER.findall(d["body"]):
            return (f"Draft #{draft_id} still has blanks: {', '.join(gaps)}\n"
                    f"Fill them with: edit {draft_id} <full reply>  or  redo {draft_id} <the details>")
        conn = self.connector(d["source"])
        if conn is None:
            return f"{d['source']} is not connected, so draft #{draft_id} can't be sent."
        if not self.store.transition_draft(draft_id, "pending", "sending"):
            return f"Draft #{draft_id} is already being handled."
        try:
            conn.send_reply(d["external_id"], d["body"])
        except Exception as exc:
            log.exception("Sending draft %s failed", draft_id)
            self.store.transition_draft(draft_id, "sending", "pending", error=str(exc)[:500])
            return f"❌ Sending draft #{draft_id} failed: {str(exc)[:200]}\nIt is still pending; try again or reply from your mailbox."
        self.store.transition_draft(draft_id, "sending", "sent")
        self.store.mark_replied(d["source"], d["thread_id"], self._now())
        self.store.log("draft_sent", draft_id=draft_id, email_id=d["email_id"])
        return f"✅ Sent reply to {sender_name(d['sender'])} (draft #{draft_id})."

    def skip_draft(self, draft_id: int) -> str:
        if self.store.transition_draft(draft_id, "pending", "skipped"):
            self.store.log("draft_skipped", draft_id=draft_id)
            return f"Skipped draft #{draft_id}. The reply deadline still applies if you answer yourself."
        d = self.store.draft(draft_id)
        return f"No draft #{draft_id}." if d is None else f"Draft #{draft_id} is already {d['status']}."

    def edit_draft(self, draft_id: int, text: str) -> str:
        if not text.strip():
            return f"Send the full new reply after the number, e.g. edit {draft_id} Hi Asha, ..."
        if not self.store.update_draft_body(draft_id, text.strip(), []):
            d = self.store.draft(draft_id)
            return f"No draft #{draft_id}." if d is None else f"Draft #{draft_id} is already {d['status']}."
        self.store.log("draft_edited", draft_id=draft_id)
        return self.format_draft(self.store.draft(draft_id))

    def redo_draft(self, draft_id: int, instruction: str) -> str:
        d = self.store.draft(draft_id)
        if d is None:
            return f"No draft #{draft_id}."
        if d["status"] != "pending":
            return f"Draft #{draft_id} is already {d['status']}."
        if not instruction.strip():
            return f"Say what to change, e.g. redo {draft_id} shorter, offer a call on Tuesday"
        conn = self.connector(d["source"])
        body = conn.fetch_body(d["external_id"]) if conn else d["summary"]
        new = self.brain.revise_draft(d["sender"], d["subject"], body, d["body"], instruction)
        self.store.update_draft_body(draft_id, new.reply, new.needs_input)
        self.store.log("draft_revised", draft_id=draft_id)
        return self.format_draft(self.store.draft(draft_id))

    # --- team -----------------------------------------------------------------------

    def notify_user(self, user, text: str, teaser: str | None = None) -> bool:
        """Message a team member on WhatsApp. The founder uses the main notifier."""
        if user is None:
            return False
        if user["id"] == self.settings.owner_id:
            self.notifier.send(text, teaser=teaser)
            return True
        if user["whatsapp"] and self.notifier_factory:
            try:
                self.notifier_factory(user["whatsapp"]).send(text, teaser=teaser)
                return True
            except Exception:
                log.exception("Could not message %s", user["id"])
        return False

    def notify_admins(self, text: str, except_id: str | None = None) -> None:
        for u in self.store.users():
            if u["role"] == "admin" and u["id"] != except_id:
                self.notify_user(u, text)

    def assign_team_task(self, by_user, assignee, title: str, due_at: datetime | None = None,
                         notes: str = "", email_id: int | None = None) -> int:
        if not title.strip():
            raise TeamError("A task needs a title.")
        if not assignee["active"]:
            raise TeamError(f"{assignee['name']} is not active on the team.")
        task_id = self.store.add_team_task(title, assignee["id"], by_user["id"], due_at, notes, email_id)
        self.store.log("team_task_created", by=by_user["id"], task_id=task_id, assignee=assignee["id"])
        if assignee["id"] != by_user["id"]:
            task = self.store.team_task(task_id)
            self.notify_user(assignee, f"📌 New task from {by_user['name']}\n{format_task(task, self.settings.tz)}"
                                       + (f"\n{notes}" if notes else "")
                                       + f"\nReply 'done {task_id}' when finished.",
                             teaser=f"New task from {by_user['name']}: {title}")
        return task_id

    def _task_for_change(self, by_user, task_id: int):
        task = self.store.team_task(task_id)
        if task is None:
            raise TeamError(f"No team task #{task_id}.")
        if not can_change(by_user, task):
            raise TeamError(f"Only {task['assignee_name']}, the person who created it, or an admin can change #{task_id}.")
        return task

    def complete_team_task(self, by_user, task_id: int) -> str:
        task = self._task_for_change(by_user, task_id)
        if task["status"] == "done":
            return f"#{task_id} is already done."
        self.store.update_team_task(task_id, actor=by_user["id"], status="done", done_at=self._now(), blocked_reason="")
        self.store.log("team_task_done", by=by_user["id"], task_id=task_id)
        creator = self.store.user(task["created_by"])
        if creator and creator["id"] != by_user["id"]:
            self.notify_user(creator, f"✅ {by_user['name']} finished #{task_id} {task['title']}")
        return f"✅ Done: #{task_id} {task['title']}"

    def block_team_task(self, by_user, task_id: int, reason: str) -> str:
        task = self._task_for_change(by_user, task_id)
        if not reason.strip():
            raise TeamError("Say what's blocking it, e.g. 'blocked 12 waiting for client logo'.")
        self.store.update_team_task(task_id, actor=by_user["id"], status="blocked", blocked_reason=reason.strip()[:300])
        self.store.log("team_task_blocked", by=by_user["id"], task_id=task_id, reason=reason[:200])
        msg = f"🚧 {by_user['name']} is blocked on #{task_id} {task['title']}\nReason: {reason.strip()}"
        self.notify_admins(msg, except_id=by_user["id"])
        creator = self.store.user(task["created_by"])
        if creator and creator["role"] != "admin" and creator["id"] != by_user["id"]:
            self.notify_user(creator, msg)
        return f"Marked #{task_id} as blocked. The admins have been told."

    def reopen_team_task(self, by_user, task_id: int) -> str:
        self._task_for_change(by_user, task_id)
        self.store.update_team_task(task_id, actor=by_user["id"], status="open", blocked_reason="", done_at=None)
        self.store.log("team_task_reopened", by=by_user["id"], task_id=task_id)
        return f"Reopened #{task_id}."

    def reassign_team_task(self, by_user, task_id: int, assignee) -> str:
        task = self._task_for_change(by_user, task_id)
        self.store.update_team_task(task_id, actor=by_user["id"], assignee_id=assignee["id"], reminded=0,
                                    overdue_alerted=0)
        self.store.log("team_task_reassigned", by=by_user["id"], task_id=task_id, to=assignee["id"])
        if assignee["id"] != by_user["id"]:
            self.notify_user(assignee, f"📌 {by_user['name']} handed you #{task_id} {task['title']}",
                             teaser=f"{by_user['name']} handed you a task: {task['title']}")
        return f"#{task_id} now belongs to {assignee['name']}."

    def team_reminders(self) -> dict[str, int]:
        """Ping assignees shortly before a due time, and tell assignee + admins once when overdue."""
        now = self._now()
        lead = timedelta(minutes=self.settings.task_reminder_lead_minutes)
        sent = {"reminded": 0, "overdue": 0}
        for t in self.store.team_tasks("open"):
            due = row_dt(t["due_at"])
            if due is None or t["status"] == "blocked":
                continue
            assignee = self.store.user(t["assignee_id"])
            if now < due <= now + lead and not t["reminded"]:
                self.notify_user(assignee, f"⏰ Due {self._fmt(due)}: #{t['id']} {t['title']}")
                self.store.update_team_task(t["id"], reminded=1)
                sent["reminded"] += 1
            elif due <= now and not t["overdue_alerted"]:
                text = f"⚠️ Overdue: {format_task(t, self.settings.tz)}"
                self.notify_user(assignee, text + f"\nReply 'done {t['id']}' or 'blocked {t['id']} <reason>'.")
                self.notify_admins(text, except_id=t["assignee_id"])
                self.store.update_team_task(t["id"], overdue_alerted=1, reminded=1)
                sent["overdue"] += 1
        if any(sent.values()):
            self.store.log("team_reminders", **sent)
        return sent

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
            "reply_drafts_waiting_for_your_approval": len(self.store.pending_drafts()),
            "goal_progress_last_7_days": compute_progress(self.store, self.settings.tz, days=7),
            "team_overdue_or_blocked": [
                format_task(t, self.settings.tz) for t in self.store.team_tasks("open")
                if t["status"] == "blocked" or (t["due_at"] and row_dt(t["due_at"]) < now)
            ][:15],
        }

    # --- calendar and reports ------------------------------------------------------------

    def meetings(self, force: bool = False) -> dict:
        from .integrations import calendar_urls
        from .pa.calendar import cached_events, meetings_view

        try:
            events = cached_events(self.store, self.settings, calendar_urls(self.settings, self.store), force=force)
        except Exception:
            log.exception("Calendar unavailable")
            events = []
        return meetings_view(self.pa, events, self.settings.tz)

    def report(self, kind: str, deliver: bool = False) -> dict:
        """Write a report (AI text when available, plain text otherwise), save it, optionally send it."""
        from .brain import goals_text
        from .pa import reports

        out = reports.generate(kind, self.store, self.settings, llm=getattr(self.brain, "llm", None),
                               goals=goals_text(self.settings.goals), meetings=self.meetings())
        if deliver:
            self.notifier.send(out["text"], teaser=f"Your {reports.TITLES[kind]} is ready. Open NeuraNova PA → Reports.")
        self._save_to_drive(out)
        return out

    def _save_to_drive(self, out: dict) -> None:
        from .integrations import save_values, with_integrations

        merged = with_integrations(self.settings, self.store)
        token = merged.secret("GDRIVE_TOKEN_JSON")
        if not token:
            return
        try:
            from .pa.drive import upload_report
            link, folder = upload_report(token, out["title"], out["text"], self.store.get("drive_folder_id") or "",
                                         on_refresh=lambda t: save_values(self.store, self.settings, "drive",
                                                                          {"GDRIVE_TOKEN_JSON": t}, "agent"))
            self.store.put("drive_folder_id", folder)
            self.store.log("report_saved_to_drive", title=out["title"], link=link)
        except Exception:
            log.exception("Could not save the report to Google Drive")

    def weekly_report(self) -> str:
        out = self.report("weekly", deliver=True)
        for kind in ("sales", "quality", "qa"):  # saved for the Reports page, not sent (no spam)
            try:
                self.report(kind)
            except Exception:
                log.exception("Could not write the %s report", kind)
        self.store.put("last_weekly_report", out["text"])
        return out["text"]

    def morning_brief(self) -> str:
        self.check_inbox()
        out = self.report("morning", deliver=True)
        self.store.put("last_brief", self._now().isoformat())
        return out["text"]

    def eod_summary(self) -> str:
        return self.report("eod", deliver=True)["text"]

    def monthly_report(self) -> str:
        return self.report("monthly", deliver=True)["text"]
