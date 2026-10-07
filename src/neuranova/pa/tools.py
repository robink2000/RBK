"""Tools that let the AI Assistant answer from NeuraNova's real data and act on work items.

Nothing here sends a message: draft_message only puts a draft in the approvals outbox.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..db import row_dt
from . import briefing, business, quality
from .dates import bucket, parse_deadline
from .store import DEPARTMENTS, KINDS, LEAD_STAGES, PRIORITIES, QA_STAGES, STATUSES, data_of

N = lambda kind, **extra: {"type": [kind, "null"], **extra}  # noqa: E731


def T(name, description, properties):
    return {"name": name, "description": description, "properties": properties}


PA_TOOLS = [
    T("attention", "What needs attention now: headline counts, focus lists and recommended next actions.", {}),
    T("list_items", "List work items (tasks, follow-ups, waiting-for, leads, application issues, quality concerns, "
      "decisions, payments) with filters.", {
        "kind": N("string", description="One of: " + ", ".join(KINDS)),
        "when": {"type": "string", "enum": ["any", "overdue", "today", "tomorrow", "this_week", "no_date"]},
        "status": {"type": "string", "enum": ["active", "waiting", "blocked", "ready_for_retest", "closed_recently"]},
        "owner": N("string", description="Teammate name, 'me', or 'unassigned'"),
        "search": N("string"),
    }),
    T("create_item", "Create a work item. For 'remind me' requests create a task owned by 'me' with the due time.", {
        "kind": {"type": "string", "enum": list(KINDS)},
        "title": {"type": "string"},
        "due": N("string", description="Natural phrase ('tomorrow 3pm', 'before Friday') or ISO date-time"),
        "owner": N("string", description="Teammate name or 'me'"),
        "priority": {"type": "string", "enum": list(PRIORITIES)},
        "department": N("string", description="One of: " + ", ".join(DEPARTMENTS)),
        "related_person": N("string"),
        "notes": N("string"),
        "repeat": N("string", description="Only if it repeats, in words: 'every Friday', 'every weekday', "
                                          "'every month on the 5th', 'every 2 weeks'"),
    }),
    T("update_item", "Update a work item by id: status, due, owner, priority, lead/QA stage, or add a note.", {
        "item_id": {"type": "integer"},
        "status": N("string", description="One of: " + ", ".join(STATUSES)),
        "due": N("string"),
        "owner": N("string"),
        "priority": N("string", description="One of: " + ", ".join(PRIORITIES)),
        "stage": N("string", description="Lead: " + ", ".join(LEAD_STAGES) + ". QA: " + ", ".join(QA_STAGES)),
        "note": N("string"),
    }),
    T("item_history", "Full details and history of one work item.", {"item_id": {"type": "integer"}}),
    T("waiting_on_others", "Promises and replies NeuraNova is waiting for, with expected dates and who.", {}),
    T("business_pipeline", "Leads: new, hot, stalled, follow-ups due, demos, admissions, payments, conversions.",
      {"days": {"type": "integer", "enum": [7, 30, 90]}}),
    T("application_qa", "Application issues by stage, fixes awaiting retest, recent Production/Development check runs.", {}),
    T("quality_status", "Quality concerns, categories and recurring patterns.", {"days": {"type": "integer", "enum": [14, 30, 90]}}),
    T("meetings", "Meetings today and in the next 7 days, with open items to prepare.", {}),
    T("recent_communication", "Summaries of recent important emails and WhatsApp messages.", {
        "hours": {"type": "integer", "enum": [24, 72, 168]}}),
    T("draft_message", "Draft a WhatsApp or email message. It goes to Approvals; it is never sent automatically.", {
        "to": {"type": "string", "description": "Contact name, phone number or email"},
        "channel": {"type": "string", "enum": ["whatsapp", "email"]},
        "purpose": {"type": "string", "description": "What the message must say or ask, with any deadline"},
        "item_id": N("integer"),
    }),
    T("get_report", "Latest report text, or a fresh one: morning, eod, weekly, monthly, sales, quality, qa.", {
        "kind": {"type": "string", "enum": ["morning", "eod", "weekly", "monthly", "sales", "quality", "qa"]},
        "fresh": {"type": "boolean"},
    }),
]
MEMBER_PA_TOOLS = [t for t in PA_TOOLS if t["name"] in (
    "attention", "list_items", "create_item", "update_item", "item_history", "waiting_on_others", "business_pipeline",
    "application_qa", "quality_status", "meetings")]


def _row(r, tz) -> dict:
    due = row_dt(r["due_at"]) if r["due_at"] else None
    out = {"id": r["id"], "kind": r["kind"], "title": r["title"], "status": r["status"], "priority": r["priority"],
           "owner": r["owner_name"] or None, "due": due.astimezone(tz).strftime("%a %d %b %H:%M") if due else None}
    for key in ("stage", "waiting_on", "related_person", "department", "next_action"):
        if r[key]:
            out[key] = r[key]
    if r["contact_name"]:
        out["contact"] = r["contact_name"]
    return out


class PATools:
    """Mixed into the Assistant; expects self.agent, self.store, self.settings, self._person(), self._me()."""

    def _pa(self):
        return self.store.pa

    def _owner_id(self, name):
        if not name:
            return None
        if name.strip().lower() == "unassigned":
            return "__none__"
        return self._person(name)["id"]

    def _due(self, text):
        if not text:
            return None
        now = datetime.now(self.settings.tz)
        try:
            dt = datetime.fromisoformat(text)
            if len(text.strip()) <= 10:     # a date without a time: end of the working day, not midnight
                dt = datetime.combine(dt.date(), self.settings.working_hours.end)
            return dt if dt.tzinfo else dt.replace(tzinfo=self.settings.tz)
        except ValueError:
            due = parse_deadline(text, now, end_of_day=self.settings.working_hours.end)
            if due is None:
                raise ValueError(f"Couldn't understand the date '{text}'. Try 'tomorrow 3pm' or '2026-10-12 15:00'.")
            return due

    def attention(self):
        b = briefing.build(self.store, self.settings, meetings=self.agent.meetings()["today"],
                           user_name=self.user["name"] if self.user else "")
        if not self.is_owner:
            mine = [r for r in self._pa().items(owner_id=self._me()["id"], limit=200)]
            return {"your_items": [_row(r, self.settings.tz) for r in mine][:30]}
        return {"headline": [f"{x['count']} {x['text']}" for x in b["headline"]],
                "recommended_actions": [f"{a['text']} ({a['why']})" for a in b["actions"]],
                "focus": {label: [f"{e['title']}" + (f" — {e['who']}" if e.get("who") else "") +
                                  (f" — {e['due']}" if e.get("due") else "") for e in b["focus"][key][:6]]
                          for key, label in briefing.FOCUS if b["focus"][key]}}

    def list_items(self, kind, when, status, owner, search):
        pa, tz = self._pa(), self.settings.tz
        now = datetime.now(tz)
        st = {"active": "active", "waiting": "waiting", "blocked": "blocked", "ready_for_retest": "ready_for_retest",
              "closed_recently": ("closed", "verified")}[status]
        rows = pa.items(kind=kind if kind in KINDS else None, status=st, owner_id=self._owner_id(owner),
                        search=search or "", limit=300)
        if status == "closed_recently":
            rows = [r for r in rows if r["completed_at"] and row_dt(r["completed_at"]) > now - timedelta(days=7)]
        if when != "any":
            rows = [r for r in rows if (bucket(row_dt(r["due_at"]) if r["due_at"] else None, now) == when)
                    or (when == "no_date" and not r["due_at"])]
        return {"count": len(rows), "items": [_row(r, tz) for r in rows[:40]]}

    def create_item(self, kind, title, due, owner, priority, department, related_person, notes, repeat=None):
        from . import recurring
        owner_id = self._person(owner)["id"] if owner else None
        rule = recurring.parse(repeat)[0] if repeat else None
        extra = {"data": {"repeat": rule, "tz": self.settings.tz.key}} if rule else {}
        dupe = self._pa().similar_open(title, kind=kind, person=related_person or "", threshold=0.75)
        if dupe is not None:
            return {"already_exists": _row(dupe, self.settings.tz),
                    "hint": "A matching open item exists; update it instead of creating a duplicate."}
        item_id = self._pa().create_item(
            self._me()["id"], kind=kind, title=title[:200], due_at=self._due(due), owner_id=owner_id,
            priority=priority, department=department if department in DEPARTMENTS else "",
            related_person=related_person or "", description=notes or "", source="chat",
            status="waiting" if kind == "waiting" else "open",
            stage="new" if kind in ("lead", "qa_issue") else "", **extra)
        if rule and not due:
            first = recurring.first_due(rule, datetime.now(self.settings.tz), self.settings.working_hours.start)
            self._pa().update_item(item_id, self._me()["id"], due_at=first)
        if owner_id and owner_id != self._me()["id"]:
            person = self.store.user(owner_id)
            self.agent.notify_user(person, f"📌 New from {self._me()['name']}: {title}" +
                                   (f"\nDue {self._due(due):%a %d %b %H:%M}" if due else ""))
        return {"created": _row(self._pa().item(item_id), self.settings.tz)}

    def update_item(self, item_id, status, due, owner, priority, stage, note):
        from ..team import TeamError, can_change
        row = self._pa().item(item_id)
        if row is None:
            raise ValueError(f"No item #{item_id}")
        if not can_change(self._me(), row):
            raise TeamError("You can only change your own items, ones you created, or (as admin) any item.")
        fields = {}
        if status:
            if status not in STATUSES:
                raise ValueError(f"Unknown status {status}")
            fields["status"] = status
        if due:
            fields["due_at"] = self._due(due)
        if owner:
            fields["owner_id"] = self._person(owner)["id"]
        if priority in PRIORITIES:
            fields["priority"] = priority
        if stage:
            if row["kind"] == "qa_issue":
                from .qa import set_stage
                set_stage(self._pa(), item_id, stage, self._me()["id"], note or "")
                note = None
            elif stage in LEAD_STAGES:
                fields["stage"] = stage
                if stage in ("converted", "lost"):
                    fields["status"] = "closed"
        self._pa().update_item(item_id, self._me()["id"], note=note or "", **fields)
        return {"updated": _row(self._pa().item(item_id), self.settings.tz)}

    def item_history(self, item_id):
        row = self._pa().item(item_id)
        if row is None:
            raise ValueError(f"No item #{item_id}")
        return {"item": _row(row, self.settings.tz), "description": row["description"],
                "history": [{"at": e["at"][:16], "by": e["actor"], "event": e["event"], "detail": e["detail"][:200]}
                            for e in self._pa().item_events(item_id)][-15:]}

    def waiting_on_others(self):
        rows = self._pa().items(kind="waiting", status="active", limit=200)
        now = datetime.now(timezone.utc)
        return [{**_row(r, self.settings.tz), "late": bool(r["due_at"] and row_dt(r["due_at"]) < now),
                 "since": r["waiting_since"][:10] if r["waiting_since"] else None} for r in rows]

    def business_pipeline(self, days):
        p = business.pipeline(self._pa(), days=days)
        tz = self.settings.tz
        return {k: ([_row(r, tz) for r in v][:15] if isinstance(v, list) else v)
                for k, v in p.items() if k != "signals"}

    def application_qa(self):
        issues = self._pa().items(kind="qa_issue", status=None, limit=500)
        open_ = [r for r in issues if r["status"] not in ("closed", "verified")]
        return {"open": [{**_row(r, self.settings.tz), "environment": data_of(r).get("environment"),
                          "occurrences": data_of(r).get("occurrences", 1)} for r in open_][:30],
                "awaiting_retest": [r["title"] for r in open_ if r["status"] == "ready_for_retest"],
                "recent_runs": [{"environment": r["environment"], "status": r["status"], "summary": r["summary"],
                                 "at": r["started_at"][:16]} for r in self._pa().qa_runs(6)]}

    def quality_status(self, days):
        q = quality.summary(self._pa(), days=days)
        return {**{k: v for k, v in q.items() if k not in ("open", "patterns")},
                "open": [_row(r, self.settings.tz) for r in q["open"]][:20],
                "patterns": [p["text"] for p in q["patterns"]]}

    def meetings(self):
        m = self.agent.meetings()
        fmt = lambda v: {"title": v["title"], "when": f"{v['day']} {v['when']}", "attendees": v["attendees"][:6],  # noqa: E731
                         "prepare": [p["title"] for p in v["prep"]]}
        return {"today": [fmt(v) for v in m["today"]], "upcoming": [fmt(v) for v in m["upcoming"]],
                "ended_without_captured_actions": [v["title"] for v in m["needs_capture"]]}

    def recent_communication(self, hours):
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        emails = [{"from": r["sender"], "subject": r["subject"], "summary": r["summary"], "priority": r["priority"],
                   "replied": bool(r["replied_at"])}
                  for r in self.store.received_since(since) if r["category"] not in ("newsletter", "spam", "notification")]
        wa = [{"from": m["contact_name"] or m["sender"], "summary": m["summary"] or m["body"][:200],
               "importance": m["importance"], "replied": bool(m["replied_at"])}
              for m in self._pa().messages("whatsapp", since=since) if m["direction"] == "in"]
        return {"emails": emails[:25], "whatsapp": wa[:25]}

    def draft_message(self, to, channel, purpose, item_id):
        pa = self._pa()
        matches = pa.contacts(to, limit=3)
        contact = matches[0] if matches else None
        if contact is not None:
            recipient = contact["phone"] if channel == "whatsapp" else contact["email"]
            name = contact["name"]
        else:
            recipient, name = to, ""
        if not recipient:
            raise ValueError(f"No {'phone number' if channel == 'whatsapp' else 'email address'} known for {to}.")
        outbox_id = self.agent.compose(channel, recipient, purpose, self._me()["id"], recipient_name=name,
                                       item_id=item_id)
        o = pa.outbox_item(outbox_id)
        return {"draft_id": outbox_id, "to": name or recipient, "channel": channel, "text": o["body"],
                "note": "Waiting in Communications → Approvals. Nothing is sent until you approve it."}

    def get_report(self, kind, fresh):
        if not fresh:
            latest = self._pa().reports(kind, limit=1)
            if latest:
                return {"title": latest[0]["title"], "text": latest[0]["text"]}
        out = self.agent.report(kind)
        return {"title": out["title"], "text": out["text"]}
