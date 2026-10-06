"""NeuraNova PA pages: Today, Tasks, Business, Communications, Application QA, Quality, Reports, AI Assistant,
Settings, first-run setup, search and the audit log. Mounted by dashboard.mount_dashboard.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from . import integrations as integ
from .connectors.gmail import sender_name
from .db import row_dt
from .pa import briefing, business, prefs, qa, quality, recurring
from .pa.dates import parse_deadline
from .pa.reports import TITLES as REPORT_TITLES
from .pa.store import (CONTACT_ROLES, DEPARTMENTS, KINDS, LEAD_STAGE_LABELS, LEAD_STAGES, PRIORITIES,
                       QA_STAGE_LABELS, QA_STAGES, QUALITY_CATEGORIES, STATUS_LABELS, STATUSES, data_of)
from .team import TeamError, can_change

log = logging.getLogger(__name__)

SETUP_STEPS = [
    ("company", "Company"), ("apps", "NeuraNova applications"), ("email", "Email"), ("whatsapp", "WhatsApp Business"),
    ("calendar", "Calendar"), ("drive", "Google Drive"), ("ai", "AI"), ("notifications", "Notifications"),
    ("accounts", "QA test accounts"), ("review", "Review & finish"),
]
SETTINGS_SECTIONS = [
    ("general", "General"), ("apps", "NeuraNova applications"), ("accounts", "Test accounts"), ("ai", "AI"),
    ("integrations", "Integrations"), ("notifications", "Notifications"), ("scheduler", "Scheduler"),
    ("security", "Security"), ("phone", "Phone access"), ("backup", "Backups"), ("people", "People"),
    ("audit", "Audit log"),
]
_qa_running: dict[str, bool] = {}


def mount_pa(app: FastAPI, w) -> None:
    """`w` carries the dashboard helpers: settings, agent_factory, store, current, page, back, guarded,
    founder, today_text, sessions, base_url."""
    settings = w.settings

    def signed_in(request: Request, admin: bool = False, owner: bool = False):
        agent = w.agent_factory()
        me, cookie = w.current(request, agent)
        if not me:
            return RedirectResponse("/login", status_code=303)
        if owner and me["id"] != settings.owner_id:
            return w.oops("Only the founder can open this page.")
        if admin and me["role"] != "admin":
            return w.oops("Admins only.")
        return agent, me, w.sessions.csrf(cookie)

    def render(name, agent, me, csrf, request, **ctx):
        return w.page(name, me=me, csrf=csrf, today=w.today_text(), msg=request.query_params.get("msg", ""),
                      is_owner=me["id"] == settings.owner_id, labels=LABELS, **ctx)

    def tz_now():
        return datetime.now(settings.tz)

    def item_view(row, me) -> dict:
        e = briefing.entry(row, tz_now())
        e.update(can_change=can_change(me, row), description=row["description"], department=row["department"],
                 owner_id=row["owner_id"], created=row_dt(row["created_at"]).astimezone(settings.tz).strftime("%d %b"),
                 data=data_of(row), value=row["value"], verification=row["verification"],
                 related_project=row["related_project"], waiting_on=row["waiting_on"])
        return e

    def due_from(text: str):
        if not text or not text.strip():
            return None
        try:
            dt = datetime.fromisoformat(text.strip())
            return dt if dt.tzinfo else dt.replace(tzinfo=settings.tz)
        except ValueError:
            due = parse_deadline(text, tz_now(), end_of_day=settings.working_hours.end)
            if due is None:
                raise TeamError(f"Couldn't understand the date '{text}'. Try 'tomorrow 3pm', 'before Friday' or 12 Oct.")
            return due

    # --- first-run setup ----------------------------------------------------------------------------

    @app.get("/setup")
    def setup(request: Request, step: int = 0):
        g = signed_in(request, owner=True)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        p = prefs.get(agent.store)
        step = step or p["setup_step"] or 1
        step = max(1, min(step, len(SETUP_STEPS)))
        cards = {c["name"]: c for c in integ.view(settings, agent.store, w.base_url(request))}
        return render("setup", agent, me, csrf, request, steps=SETUP_STEPS, step=step, key=SETUP_STEPS[step - 1][0],
                      prefs=p, cards=cards, qa_cfg=integ.qa_config(settings, agent.store), roles=qa.ROLES,
                      ai=integ.ai_choice(settings, agent.store), progress=integ.summary(list(cards.values())),
                      settings_view=_settings_view(agent))

    @app.post("/setup/{step}")
    async def setup_save(request: Request, step: int):
        form = await request.form()
        g = w.guarded(request, form.get("csrf", ""))
        if isinstance(g, Response):
            return g
        agent, me = g
        if me["id"] != settings.owner_id:
            return w.oops("Only the founder can run setup.")
        key = SETUP_STEPS[max(1, min(step, len(SETUP_STEPS))) - 1][0]
        if form.get("action") != "skip":
            try:
                _save_section(agent, me, key, form)
            except (TeamError, ValueError) as exc:
                return w.back(f"/setup?step={step}", str(exc))
        nxt = step + 1
        if key == "review" or nxt > len(SETUP_STEPS):
            prefs.save(agent.store, {"setup_done": True, "setup_step": len(SETUP_STEPS)}, me["id"])
            return w.back("/", "Setup finished. NeuraNova PA is watching your business now.")
        prefs.save(agent.store, {"setup_step": nxt}, me["id"])
        return RedirectResponse(f"/setup?step={nxt}", status_code=303)

    # --- Today -----------------------------------------------------------------------------------------

    @app.get("/today")
    def today_page(request: Request):
        g = signed_in(request)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        meet = agent.meetings()
        is_owner = me["id"] == settings.owner_id
        b = agent.briefing(meetings=meet["today"], user_name=me["name"]) if is_owner else None
        if b:  # let the founder tick items off straight from Today
            for entries in b["focus"].values():
                for e in entries:
                    if e.get("kind") in KINDS and e.get("id"):
                        row = agent.pa.item(e["id"])
                        e["can_change"] = bool(row and can_change(me, row))
        mine = [item_view(r, me) for r in agent.pa.items(owner_id=me["id"], limit=200)]
        todoist, todoist_error = [], ""
        if is_owner and agent.todoist:
            try:
                for t in agent.todoist.today_and_overdue():
                    todoist.append({"content": t.content, "label": t.label, "url": t.url, "due": t.due_date or ""})
            except Exception:
                todoist_error = "Couldn't reach Todoist right now."
        return render("today", agent, me, csrf, request, b=b, meetings=meet, mine=mine, todoist=todoist,
                      todoist_error=todoist_error, members=agent.store.users())

    @app.post("/meetings/capture")
    async def capture(request: Request):
        form = await request.form()
        g = w.guarded(request, form.get("csrf", ""))
        if isinstance(g, Response):
            return g
        agent, me = g
        from .pa.calendar import capture_actions
        uid = form.get("uid", "")
        events = {e["uid"]: e for e in (agent.meetings()["today"] + agent.meetings()["upcoming"])}
        event = events.get(uid) or {"uid": uid, "title": form.get("title", "Meeting")}
        owner = form.get("owner") or None
        ids = capture_actions(agent.pa, event, (form.get("actions") or "").splitlines(), me["id"], owner_id=owner,
                              due=due_from(form.get("due", "")) if form.get("due") else None)
        return w.back("/today#meetings", f"Captured {len(ids)} action(s) from {event['title']}.")

    # --- Tasks -------------------------------------------------------------------------------------------

    @app.get("/tasks")
    def tasks_page(request: Request, kind: str = "", status: str = "active", owner: str = "", department: str = "",
                   q: str = "", when: str = ""):
        g = signed_in(request)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        st = {"active": "active", "all": None, "closed": ("closed", "verified")}.get(status, status if status in STATUSES else "active")
        owner_id = me["id"] if owner == "me" else owner or None
        rows = agent.pa.items(kind=kind or None, status=st, owner_id=owner_id, department=department or None,
                              search=q, limit=500)
        items = [item_view(r, me) for r in rows]
        if when:
            items = [i for i in items if i["bucket"] == when]
        active = agent.pa.items(limit=3000)
        now = datetime.now(timezone.utc)
        week_end = now + timedelta(days=7)
        by_owner: dict[str, dict] = {}
        for r in active:
            name = r["owner_name"] or "Unassigned"
            o = by_owner.setdefault(name, {"id": r["owner_id"] or "__none__", "open": 0, "overdue": 0, "waiting": 0,
                                           "blocked": 0, "week": 0, "done": 0})
            due = row_dt(r["due_at"]) if r["due_at"] else None
            o["open"] += 1
            o["overdue"] += bool(due and due < now)
            o["waiting"] += r["status"] == "waiting"
            o["blocked"] += r["status"] == "blocked"
            o["week"] += bool(due and now <= due <= week_end)
        for r in agent.pa.items_completed_between(now - timedelta(days=7), now):
            name = r["owner_name"] or "Unassigned"
            by_owner.setdefault(name, {"id": r["owner_id"] or "__none__", "open": 0, "overdue": 0, "waiting": 0,
                                       "blocked": 0, "week": 0, "done": 0})["done"] += 1
        return render("tasks", agent, me, csrf, request, items=items, members=agent.store.users(), by_owner=by_owner,
                      f={"kind": kind, "status": status, "owner": owner, "department": department, "q": q, "when": when})

    @app.post("/tasks/quick")
    async def task_quick(request: Request):
        """One box: "Call Ravi's parents tomorrow 3pm". The date is understood from the words; it's yours."""
        form = await request.form()
        g = w.guarded(request, form.get("csrf", ""))
        if isinstance(g, Response):
            return g
        agent, me = g
        text = " ".join((form.get("text") or "").split())[:200]
        back_to = _same_site(form.get("back") or request.headers.get("referer", ""), "/tasks")
        if not text:
            return w.back(back_to, "Type what needs doing.")
        kind = form.get("kind") if form.get("kind") in KINDS else "task"
        dupe = agent.pa.similar_open(text, kind=kind, threshold=0.8)
        if dupe is not None:
            return w.back(f"/tasks/{dupe['id']}", f"This is already open as #{dupe['id']}, so it wasn't added twice.")
        rule, title = recurring.parse(text)
        due = parse_deadline(title if rule else text, tz_now(), end_of_day=settings.working_hours.end)
        extra: dict = {}
        if rule:
            at = due.astimezone(settings.tz).time() if due and due.astimezone(settings.tz).time() != settings.working_hours.end \
                else settings.working_hours.start
            due = recurring.first_due(rule, tz_now(), at)
            extra["data"] = {"repeat": rule, "tz": settings.tz.key}
            text = title
        if kind == "waiting":
            extra.update(status="waiting", waiting_since=datetime.now(timezone.utc))
        elif kind in ("lead", "qa_issue"):
            extra["stage"] = "new"
        item_id = agent.pa.create_item(me["id"], kind=kind, title=text, due_at=due, source="manual",
                                       owner_id=me["id"], **extra)
        when = f", due {due.astimezone(settings.tz):%a %d %b %H:%M}" if due else ""
        if rule:
            when += f", repeats {recurring.describe(rule)}"
        return w.back(back_to, f"Added #{item_id}{when}. Open it to add details.")

    @app.post("/tasks")
    async def task_create(request: Request):
        form = await request.form()
        g = w.guarded(request, form.get("csrf", ""))
        if isinstance(g, Response):
            return g
        agent, me = g
        title = (form.get("title") or "").strip()
        kind = form.get("kind") if form.get("kind") in KINDS else "task"
        if not title:
            return w.back("/tasks", "Give the item a title.")
        try:
            due = due_from(form.get("due", ""))
        except TeamError as exc:
            return w.back("/tasks", str(exc))
        extra: dict = {}
        owner_id = form.get("owner") or None
        if owner_id and agent.store.user(owner_id) is None:
            owner_id = None
        repeat = form.get("repeat") if form.get("repeat") in dict(recurring.CHOICES) and form.get("repeat") else None
        if repeat:
            extra["data"] = {**extra.get("data", {}), "repeat": repeat, "tz": settings.tz.key}
            if due is None:
                due = recurring.first_due(repeat, tz_now(), settings.working_hours.start)
        dupe = agent.pa.similar_open(title, kind=kind, threshold=0.8)
        if dupe is not None and form.get("force") != "1":
            return w.back(f"/tasks/{dupe['id']}", f"This looks like #{dupe['id']}, which is already open. "
                                                  "It wasn't duplicated; update it here instead.")
        if kind == "quality" and form.get("category") in QUALITY_CATEGORIES:
            extra["data"] = {**extra.get("data", {}), "category": form["category"]}
        if kind == "lead" and (form.get("value") or "").strip():
            try:
                extra["value"] = float(form["value"].replace(",", ""))
            except ValueError:
                return w.back(form.get("back") or "/tasks", "Value should be a number, like 25000.")
        item_id = agent.pa.create_item(
            me["id"], **extra, kind=kind, title=title[:200], due_at=due, owner_id=owner_id,
            priority=form.get("priority") if form.get("priority") in PRIORITIES else "medium",
            department=form.get("department") if form.get("department") in DEPARTMENTS else "",
            related_person=(form.get("related_person") or "")[:120], description=(form.get("notes") or "")[:2000],
            status="waiting" if kind == "waiting" else "open", stage="new" if kind in ("lead", "qa_issue") else "",
            waiting_on=(form.get("related_person") or "")[:120] if kind == "waiting" else "",
            waiting_since=datetime.now(timezone.utc) if kind == "waiting" else None, source="manual")
        if owner_id and owner_id != me["id"]:
            agent.notify_user(agent.store.user(owner_id), f"📌 New from {me['name']}: {title}" +
                              (f"\nDue {due:%a %d %b %H:%M}" if due else ""))
        return w.back(form.get("back") or "/tasks", f"Added #{item_id}: {title}")

    @app.get("/tasks/{item_id}")
    def task_detail(request: Request, item_id: int):
        g = signed_in(request)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        row = agent.pa.item(item_id)
        if row is None:
            return w.back("/tasks", f"No item #{item_id}.")
        events = [{"at": row_dt(e["at"]).astimezone(settings.tz).strftime("%d %b %H:%M"), "actor": _actor(agent, e["actor"]),
                   "event": e["event"], "detail": _event_text(e, agent)} for e in agent.pa.item_events(item_id)]
        contact = agent.pa.contact(row["contact_id"]) if row["contact_id"] else None
        return render("task", agent, me, csrf, request, i=item_view(row, me), events=events, members=agent.store.users(),
                      contact=contact, evidence=_evidence(row))

    @app.post("/tasks/{item_id}")
    async def task_update(request: Request, item_id: int):
        form = await request.form()
        g = w.guarded(request, form.get("csrf", ""))
        if isinstance(g, Response):
            return g
        agent, me = g
        row = agent.pa.item(item_id)
        if row is None:
            return w.back("/tasks", f"No item #{item_id}.")
        if not can_change(me, row):
            return w.back(f"/tasks/{item_id}", "You can change your own items, ones you created, or any item as admin.")
        action = form.get("action", "save")
        fields: dict = {}
        try:
            if action == "save":
                for key in ("title", "description", "related_person", "next_action", "waiting_on", "related_project"):
                    if key in form:
                        fields[key] = (form.get(key) or "").strip()[:2000 if key == "description" else 200]
                if form.get("priority") in PRIORITIES:
                    fields["priority"] = form["priority"]
                if form.get("department") in DEPARTMENTS + ("",):
                    fields["department"] = form["department"]
                if form.get("status") in STATUSES:
                    fields["status"] = form["status"]
                if "owner" in form:
                    fields["owner_id"] = form["owner"] or None
                if form.get("due", "").strip():
                    fields["due_at"] = due_from(form["due"])
                elif form.get("clear_due"):
                    fields["due_at"] = None
                if row["kind"] == "lead" and form.get("stage") in LEAD_STAGES:
                    fields["stage"] = form["stage"]
                    if form["stage"] in ("converted", "lost"):
                        fields["status"] = "closed"
                        if form.get("lost_reason"):
                            data = data_of(row)
                            data["lost_reason"] = form["lost_reason"][:120]
                            fields["data"] = data
                if row["kind"] == "lead" and form.get("value", "").strip():
                    fields["value"] = float(form["value"].replace(",", ""))
                if "repeat" in form:
                    data = fields.get("data") or data_of(row)
                    rule = form.get("repeat") or ""
                    if rule != (data.get("repeat") or "") and (not rule or rule in dict(recurring.CHOICES) or re.fullmatch(r"(weekly:[0-6]|monthly:\d{1,2})", rule)):
                        if rule:
                            data.update(repeat=rule, tz=settings.tz.key)
                        else:
                            data.pop("repeat", None)
                        fields["data"] = data
                if row["kind"] == "quality" and form.get("category") in QUALITY_CATEGORIES:
                    data = fields.get("data") or data_of(row)
                    data["category"] = form["category"]
                    fields["data"] = data
                agent.pa.update_item(item_id, me["id"], note=(form.get("note") or "").strip()[:1000], **fields)
                if fields.get("owner_id") and fields["owner_id"] not in (row["owner_id"], me["id"]):
                    agent.notify_user(agent.store.user(fields["owner_id"]), f"📌 {me['name']} gave you #{item_id}: {row['title']}")
                msg = "Saved."
            elif action == "snooze":
                due = row_dt(row["due_at"]) if row["due_at"] else None
                local = due.astimezone(settings.tz) if due else None
                tomorrow = (tz_now() + timedelta(days=1)).date()
                at = local.timetz() if local else settings.working_hours.start.replace(tzinfo=settings.tz)
                new_due = datetime.combine(tomorrow, at.replace(tzinfo=None), settings.tz)
                agent.pa.update_item(item_id, me["id"], note="Moved to tomorrow", due_at=new_due, overdue_alerted=0)
                msg = f"Moved to tomorrow {new_due:%H:%M}."
            elif action == "qa_stage":
                qa.set_stage(agent.pa, item_id, form.get("stage", ""), me["id"], (form.get("note") or "")[:500])
                msg = f"Moved to {QA_STAGE_LABELS.get(form.get('stage', ''), form.get('stage'))}."
            elif action in ("done", "reopen", "block"):
                status = {"done": "closed", "reopen": "open", "block": "blocked"}[action]
                if action == "done" and row["kind"] == "qa_issue":
                    qa.set_stage(agent.pa, item_id, "ready_for_test", me["id"], "Marked fixed; waiting for QA retest")
                    return w.back(f"/tasks/{item_id}", "Marked fixed. It now waits for a QA retest before it's verified.")
                extra = {}
                if action == "block":
                    data = data_of(row)
                    data["blocked_reason"] = (form.get("reason") or "")[:300]
                    extra["data"] = data
                agent.pa.update_item(item_id, me["id"], note=(form.get("reason") or "")[:300], status=status, **extra)
                if action == "block":
                    agent.notify_admins(f"🚧 {me['name']} is blocked on #{item_id} {row['title']}: {form.get('reason', '')}",
                                        except_id=me["id"])
                msg = {"done": "Done.", "reopen": "Reopened.", "block": "Marked blocked; admins told."}[action]
            elif action == "followup":
                contact = agent.pa.contact(row["contact_id"]) if row["contact_id"] else None
                channel = form.get("channel", "whatsapp")
                recipient = (form.get("recipient") or "").strip() or (
                    (contact["phone"] if channel == "whatsapp" else contact["email"]) if contact else "")
                if not recipient:
                    return w.back(f"/tasks/{item_id}", "Add a phone number or email address to draft a message.")
                purpose = (form.get("purpose") or "").strip() or f"Follow up on: {row['title']}"
                agent.compose(channel, recipient, purpose, me["id"], recipient_name=contact["name"] if contact else "",
                              item_id=item_id, subject=row["title"][:80])
                return w.back("/communications#approvals", "Draft ready. Check it and approve to send.")
            else:
                msg = "Nothing changed."
        except (TeamError, ValueError) as exc:
            return w.back(f"/tasks/{item_id}", str(exc))
        return w.back(form.get("back") or f"/tasks/{item_id}", msg)

    # --- Business ---------------------------------------------------------------------------------------

    @app.get("/business")
    def business_page(request: Request, days: int = 30):
        g = signed_in(request)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        days = days if days in (7, 30, 90) else 30
        p = business.pipeline(agent.pa, days=days)
        view = lambda rows: [item_view(r, me) | {"signals": p["signals"].get(r["id"], [])} for r in rows]  # noqa: E731
        stages = [(s, LEAD_STAGE_LABELS[s], view([r for r in agent.pa.items(kind="lead", status=None, limit=3000)
                                                   if (r["stage"] or "new") == s and (r["status"] != "closed" or s in ("converted", "lost"))]))
                  for s in LEAD_STAGES]
        from .progress import compute
        goals = compute(agent.store, settings.tz, days=days)
        return render("business", agent, me, csrf, request, p=p, days=days, stages=stages, hot=view(p["hot"]),
                      stalled=view(p["stalled"]), follow=view(p["follow_ups_due"]), pay=view(p["payment_pending"]),
                      goals=goals, members=agent.store.users(), kinds=_event_kinds(), events=agent.store.recent_events(10))

    # --- Communications (founder) ---------------------------------------------------------------------------

    @app.get("/communications")
    def comms_page(request: Request, contact: int = 0):
        g = signed_in(request, owner=True)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=7)
        drafts = [{"id": d["id"], "to": sender_name(d["sender"]), "subject": d["subject"], "summary": d["summary"],
                   "body": d["body"], "needs": json.loads(d["needs_input"] or "[]")} for d in agent.store.pending_drafts()]
        outbox = [dict(o) for o in agent.pa.outbox("pending")]
        sent = [dict(o) for o in agent.pa.outbox("sent", limit=10)]
        waiting_email = [{"from": sender_name(r["sender"]), "subject": r["subject"], "summary": r["summary"],
                          "deadline": agent._fmt_deadline(r), "link": r["link"],
                          "overdue": bool(r["reply_deadline"] and row_dt(r["reply_deadline"]) < now)}
                         for r in agent.store.awaiting_reply()[:30]]
        emails = [{"from": sender_name(r["sender"]), "subject": r["subject"], "summary": r["summary"] or r["snippet"][:140],
                   "category": r["category"], "priority": r["priority"], "replied": bool(r["replied_at"]),
                   "at": row_dt(r["received_at"]).astimezone(settings.tz).strftime("%a %d %b %H:%M"), "link": r["link"]}
                  for r in reversed(agent.store.received_since(since))][:60]
        wa = [{"id": m["id"], "who": m["contact_name"] or m["sender"], "body": m["body"], "summary": m["summary"],
               "importance": m["importance"], "direction": m["direction"], "replied": bool(m["replied_at"]),
               "at": row_dt(m["at"]).astimezone(settings.tz).strftime("%a %d %b %H:%M"), "contact_id": m["contact_id"]}
              for m in agent.pa.messages("whatsapp", since=now - timedelta(days=14), contact_id=contact or None, limit=100)]
        contacts = [dict(c) for c in agent.pa.contacts(limit=300)]
        return render("communications", agent, me, csrf, request, drafts=drafts, outbox=outbox, sent=sent,
                      waiting_email=waiting_email, emails=emails, wa=wa, contacts=contacts, roles=CONTACT_ROLES,
                      safe_mode=prefs.safe_mode(agent.store), contact_filter=contact)

    @app.post("/outbox/compose")
    async def compose(request: Request):
        form = await request.form()
        g = w.guarded(request, form.get("csrf", ""))
        if isinstance(g, Response):
            return g
        agent, me = g
        if me["id"] != settings.owner_id:
            return w.oops("Only the founder can message people from here.")
        recipient = (form.get("recipient") or "").strip()
        purpose = (form.get("purpose") or "").strip()
        if not recipient or not purpose:
            return w.back("/communications#compose", "Enter who it's for and what it should say.")
        name = ""
        if contact := agent.pa.contacts(recipient, limit=1):
            name = contact[0]["name"]
            recipient = (contact[0]["phone"] if form.get("channel") == "whatsapp" else contact[0]["email"]) or recipient
        agent.compose(form.get("channel", "whatsapp"), recipient, purpose, me["id"], recipient_name=name,
                      subject=(form.get("subject") or "")[:120])
        return w.back("/communications#approvals", "Draft ready. Check it and approve to send.")

    @app.post("/outbox/{outbox_id}/{action}")
    async def outbox_action(request: Request, outbox_id: int, action: str):
        form = await request.form()
        g = w.guarded(request, form.get("csrf", ""))
        if isinstance(g, Response):
            return g
        agent, me = g
        if me["id"] != settings.owner_id:
            return w.oops("Only the founder can approve outgoing messages.")
        if action == "send":
            msg = agent.send_outbox(outbox_id, me["id"], body=form.get("body"))
        elif action == "reject":
            msg = agent.reject_outbox(outbox_id, me["id"])
        else:
            return w.back("/communications#approvals", "Unknown action.")
        return w.back("/communications#approvals", msg)

    @app.post("/contacts/{contact_id}")
    async def contact_save(request: Request, contact_id: int):
        form = await request.form()
        g = w.guarded(request, form.get("csrf", ""))
        if isinstance(g, Response):
            return g
        agent, me = g
        agent.pa.update_contact(contact_id, **{k: (form.get(k) or "").strip()[:300] for k in
                                               ("name", "email", "phone", "organization", "role", "notes") if k in form})
        return w.back("/communications#contacts", "Contact saved.")

    # --- Application QA ---------------------------------------------------------------------------------------

    @app.get("/qa")
    def qa_page(request: Request):
        g = signed_in(request)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        issues = [item_view(r, me) for r in agent.pa.items(kind="qa_issue", status=None, limit=1000)
                  if r["status"] != "closed"]
        by_stage = [(s, QA_STAGE_LABELS[s], [i for i in issues if (i["stage"] or "new") == s]) for s in QA_STAGES if s != "closed"]
        runs = []
        for r in agent.pa.qa_runs(15):
            results = json.loads(r["results"] or "[]")
            runs.append({**dict(r), "results": results,
                         "started": row_dt(r["started_at"]).astimezone(settings.tz).strftime("%a %d %b %H:%M")})
        cfg = integ.qa_config(settings, agent.store)
        return render("qa", agent, me, csrf, request, by_stage=by_stage, runs=runs, cfg=cfg, running=dict(_qa_running),
                      envs=qa.ENVIRONMENTS, open_count=len(issues))

    @app.post("/qa/run/{environment}")
    def qa_run(request: Request, environment: str, csrf: str = Form("")):
        g = w.guarded(request, csrf)
        if isinstance(g, Response):
            return g
        agent, me = g
        if environment not in qa.ENVIRONMENTS:
            return w.back("/qa", "Unknown environment.")
        if _qa_running.get(environment):
            return w.back("/qa", "Checks are already running there.")

        def go():
            _qa_running[environment] = True
            try:
                w.agent_factory().run_qa(environment)
            except Exception:
                log.exception("QA run failed")
            finally:
                _qa_running.pop(environment, None)

        threading.Thread(target=go, daemon=True).start()
        return w.back("/qa", f"Checks started on {qa.ENVIRONMENTS[environment]}. Refresh in a minute for results.")

    @app.get("/qa/evidence/{run_id}/{name}")
    def qa_evidence(request: Request, run_id: int, name: str):
        g = signed_in(request)
        if isinstance(g, Response):
            return g
        if not re.fullmatch(r"[a-z0-9-]+\.png", name):
            return Response(status_code=404)
        base = Path(settings.db_path).parent if str(settings.db_path) != ":memory:" else Path("data")
        path = (base / "qa" / f"run-{run_id}" / name).resolve()
        if not str(path).startswith(str((base / "qa").resolve())) or not path.exists():
            return Response(status_code=404)
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})

    # --- Quality ---------------------------------------------------------------------------------------------

    @app.get("/quality")
    def quality_page(request: Request, days: int = 30):
        g = signed_in(request)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        days = days if days in (14, 30, 90) else 30
        q = quality.summary(agent.pa, days=days)
        by_cat: dict[str, list] = {}
        for r in q["open"]:
            by_cat.setdefault(data_of(r).get("category") or "Uncategorised", []).append(item_view(r, me))
        return render("quality", agent, me, csrf, request, q=q, days=days, by_cat=by_cat, categories=QUALITY_CATEGORIES,
                      members=agent.store.users())

    # --- Reports ------------------------------------------------------------------------------------------------

    @app.get("/reports")
    def reports_page(request: Request, kind: str = ""):
        g = signed_in(request, admin=True)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        rows = [{**dict(r), "created": row_dt(r["created_at"]).astimezone(settings.tz).strftime("%a %d %b %H:%M")}
                for r in agent.pa.reports(kind or None, limit=60)]
        from .chart_helpers import goal_charts
        return render("reports", agent, me, csrf, request, rows=rows, kinds=REPORT_TITLES, kind=kind,
                      charts=goal_charts(agent.store, settings))

    @app.get("/reports/{report_id}")
    def report_view(request: Request, report_id: int):
        g = signed_in(request, admin=True)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        r = agent.pa.report(report_id)
        if r is None:
            return w.back("/reports", "Report not found.")
        return render("report", agent, me, csrf, request, r=dict(r),
                      created=row_dt(r["created_at"]).astimezone(settings.tz).strftime("%A %d %B %Y %H:%M"))

    @app.post("/reports/generate")
    def report_generate(request: Request, csrf: str = Form(""), kind: str = Form(...)):
        g = w.guarded(request, csrf, admin=True)
        if isinstance(g, Response):
            return g
        agent, me = g
        if kind not in REPORT_TITLES:
            return w.back("/reports", "Unknown report.")
        out = agent.report(kind)
        return w.back(f"/reports/{out['id']}", f"{REPORT_TITLES[kind]} ready" + ("" if out["ai"] else " (plain version; AI not connected)") + ".")

    # --- AI Assistant -----------------------------------------------------------------------------------------------

    @app.get("/assistant")
    def assistant_page(request: Request):
        g = signed_in(request)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        role = "founder" if me["id"] == settings.owner_id else f"member:{me['id']}"
        history = [{"who": "you" if r["role"] == role else "pa", "text": r["text"],
                    "at": row_dt(r["at"]).astimezone(settings.tz).strftime("%a %H:%M")}
                   for r in agent.store.recent_chat(30, role_prefix=(role, f"agent>{role}"))]
        return render("assistant", agent, me, csrf, request, history=history, ai=integ.ai_choice(settings, agent.store))

    @app.post("/assistant/ask")
    async def assistant_ask(request: Request):
        form = await request.form()
        g = w.guarded(request, form.get("csrf", ""))
        if isinstance(g, Response):
            return JSONResponse({"error": "Your session expired. Reload the page and sign in again."}, status_code=403)
        agent, me = g
        text = (form.get("text") or "").strip()[:2000]
        if not text:
            return JSONResponse({"error": "Type a question first."}, status_code=400)
        from .assistant import Assistant
        from .commands import handle
        try:
            reply = handle(agent, text, chat=lambda t: Assistant(agent, user=me).reply(t), user=me)
        except Exception as exc:
            log.exception("Assistant failed")
            return JSONResponse({"error": f"The AI couldn't answer ({str(exc)[:120]}). Check Settings → AI."}, status_code=502)
        return JSONResponse({"reply": reply})

    # --- Search ------------------------------------------------------------------------------------------------------

    @app.get("/search")
    def search(request: Request, q: str = ""):
        g = signed_in(request)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        q = q.strip()[:100]
        items = [item_view(r, me) for r in agent.pa.items(status=None, search=q, limit=50)] if q else []
        is_owner = me["id"] == settings.owner_id
        contacts = [dict(c) for c in agent.pa.contacts(q, limit=20)] if q and is_owner else []
        emails = [{"from": sender_name(r["sender"]), "subject": r["subject"], "summary": r["summary"]}
                  for r in agent.store.search_emails(q, 20)] if q and is_owner else []
        return render("search", agent, me, csrf, request, q=q, items=items, contacts=contacts, emails=emails)

    @app.get("/export/{what}.csv")
    def export_csv(request: Request, what: str, kind: str = "", status: str = "active", owner: str = "",
                   department: str = "", q: str = ""):
        g = signed_in(request, owner=(what == "contacts"))
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        import csv
        import io
        buf = io.StringIO()
        writer = csv.writer(buf)
        out = type("Out", (), {"writerow": staticmethod(lambda row: writer.writerow([_cell(c) for c in row]))})
        tz = settings.tz

        def when(v):
            return row_dt(v).astimezone(tz).strftime("%Y-%m-%d %H:%M") if v else ""

        if what in ("tasks", "leads"):
            st = {"active": "active", "all": None, "closed": ("closed", "verified")}.get(status, status if status in STATUSES else "active")
            rows = agent.pa.items(kind="lead" if what == "leads" else (kind or None), status=None if what == "leads" else st,
                                  owner_id=(me["id"] if owner == "me" else owner or None), department=department or None,
                                  search=q, limit=5000)
            out.writerow(["ID", "Type", "Title", "Status", "Stage", "Priority", "Owner", "Person", "Department", "Due",
                          "Value", "Repeats", "Created", "Completed", "Details"])
            for r in rows:
                out.writerow([r["id"], KINDS.get(r["kind"], r["kind"]), r["title"], STATUS_LABELS.get(r["status"], r["status"]),
                              LEAD_STAGE_LABELS.get(r["stage"]) or QA_STAGE_LABELS.get(r["stage"], r["stage"] or ""),
                              r["priority"], r["owner_name"] or "", r["waiting_on"] or r["related_person"] or r["contact_name"] or "",
                              r["department"], when(r["due_at"]), "" if r["value"] is None else r["value"],
                              recurring.describe(data_of(r).get("repeat")), when(r["created_at"]), when(r["completed_at"]),
                              r["description"]])
        elif what == "contacts":
            out.writerow(["Name", "Phone", "Email", "Organisation", "Role", "Notes"])
            for c in agent.pa.contacts(limit=10000):
                out.writerow([c["name"], c["phone"], c["email"], c["organization"], c["role"], c["notes"]])
        else:
            return Response(status_code=404)
        name = f"neuranova-{what}-{datetime.now(tz):%Y%m%d}.csv"
        return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})

    @app.get("/backups/{name}")
    def backup_download(request: Request, name: str):
        g = signed_in(request, owner=True)
        if isinstance(g, Response):
            return g
        from .pa import backup
        path = backup.path_for(settings, name)
        if path is None:
            return w.back("/settings?section=backup", "That backup isn't there any more.")
        return FileResponse(path, media_type="application/zip", filename=name)

    # --- Settings ---------------------------------------------------------------------------------------------------------

    @app.get("/settings")
    def settings_page(request: Request, section: str = "general"):
        g = signed_in(request, admin=True)
        if isinstance(g, Response):
            return g
        agent, me, csrf = g
        is_owner = me["id"] == settings.owner_id
        if section == "integrations":
            return RedirectResponse("/integrations", status_code=303)
        if section == "people":
            return RedirectResponse("/team#people", status_code=303)
        if not is_owner and section not in ("audit",):
            section = "audit"
        ctx = {"section": section, "sections": SETTINGS_SECTIONS, "prefs": prefs.get(agent.store),
               "settings_view": _settings_view(agent), "qa_cfg": integ.qa_config(settings, agent.store),
               "roles": qa.ROLES, "envs": qa.ENVIRONMENTS, "ai": integ.ai_choice(settings, agent.store)}
        if section == "ai":
            ctx["cards"] = {c["name"]: c for c in integ.view(settings, agent.store, w.base_url(request))}
        if section == "backup":
            from .pa import backup
            ctx["backups"] = backup.listing(settings, settings.tz)
            ctx["backup_folder"] = str(backup.folder(settings) or "")
        if section == "phone":
            ip = _lan_ip()
            port = int(settings.secret("WEBHOOK_PORT") or 8080)
            ctx["lan_url"] = f"http://{ip}:{port}" if ip else ""
        if section == "audit":
            rows = agent.store.recent_activity(300)
            ctx["audit"] = [{"at": row_dt(a["at"]).astimezone(settings.tz).strftime("%d %b %H:%M"),
                             "action": a["action"].replace("_", " "), "detail": _audit_detail(a["detail"])} for a in rows]
        return render("settings", agent, me, csrf, request, **ctx)

    @app.post("/settings/{section}")
    async def settings_save(request: Request, section: str):
        form = await request.form()
        g = w.guarded(request, form.get("csrf", ""))
        if isinstance(g, Response):
            return g
        agent, me = g
        if me["id"] != settings.owner_id:
            return w.oops("Only the founder can change settings.")
        try:
            msg = _save_section(agent, me, section, form)
        except (TeamError, ValueError) as exc:
            return w.back(f"/settings?section={section}", str(exc))
        return w.back(f"/settings?section={section}", msg or "Saved.")

    def _save_section(agent, me, key, form) -> str:
        store = agent.store
        if key in ("company", "general"):
            tz = (form.get("timezone") or "").strip()
            if tz:
                from zoneinfo import ZoneInfo
                try:
                    ZoneInfo(tz)
                except Exception as exc:
                    raise ValueError(f'"{tz}" is not a timezone. Example: Asia/Kolkata') from exc
            hours = form.get("reply_hours") or ""
            prefs.save(store, {
                "company_name": (form.get("company_name") or "NeuraNova").strip()[:60], "timezone": tz,
                "work_start": form.get("work_start") or "", "work_end": form.get("work_end") or "",
                "work_days": [d for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun") if form.get(f"day_{d}")],
                "reply_hours": float(hours) if hours else None}, me["id"])
            return "Saved. New hours apply now; schedule times apply after the console restarts."
        if key == "apps":
            urls = {k: (form.get(k) or "").strip().rstrip("/") for k in ("NEURANOVA_PROD_URL", "NEURANOVA_DEV_URL")}
            for name, url in urls.items():
                if url and not re.match(r"^https?://", url):
                    raise ValueError("Addresses must start with https:// (or http:// for a local test server).")
            integ.save_values(store, settings, "apps", {
                **{k: v or None for k, v in urls.items()},
                "NEURANOVA_LOGIN_PATH": (form.get("NEURANOVA_LOGIN_PATH") or "").strip() or None,
                "QA_ALLOW_PROD_LOGIN": "1" if form.get("QA_ALLOW_PROD_LOGIN") else "0",
                "QA_WORKFLOWS": (form.get("QA_WORKFLOWS") or "").strip() or None}, me["id"])
            flows = qa.parse_workflows(form.get("QA_WORKFLOWS") or "")
            bad = [s for f in flows for s in f.steps if s.split(None, 1)[0].lower() not in qa.ALL_STEPS]
            return "Saved." + (f" Note: {len(bad)} step(s) use an unknown word and will fail: {bad[0]}" if bad else "")
        if key == "accounts":
            current = integ.qa_config(settings, store)["accounts"]
            for env_key in qa.ENVIRONMENTS:
                for role in qa.ROLES:
                    slug = f"{env_key}__{role.replace(' ', '_')}"
                    user = (form.get(f"{slug}__user") or "").strip()
                    pw = form.get(f"{slug}__pass") or ""
                    acct = dict(current.get(env_key, {}).get(role, {}))
                    if form.get(f"{slug}__clear"):
                        current.setdefault(env_key, {}).pop(role, None)
                        continue
                    if user:
                        acct["username"] = user
                    if pw:
                        acct["password"] = pw
                    if acct.get("username"):
                        current.setdefault(env_key, {})[role] = acct
            integ.save_values(store, settings, "apps", {"QA_ACCOUNTS_JSON": json.dumps(current)}, me["id"])
            return "Test accounts saved (encrypted)."
        if key == "ai":
            provider = form.get("provider")
            if provider in ("claude", "openai"):
                integ.save_values(store, settings, "ai", {"AI_PROVIDER": provider}, me["id"])
            for name, fields in (("claude", ("ANTHROPIC_API_KEY",)), ("openai", ("OPENAI_API_KEY", "OPENAI_MODEL"))):
                values = {f: (form.get(f) or "").strip() for f in fields if not integ.from_env(settings, f)}
                if any(values.values()):
                    integ.save_values(store, settings, name, values, me["id"])
                    ok, message = integ.run_check(name, settings, store)
                    if not ok:
                        raise ValueError(f"{'Claude' if name == 'claude' else 'OpenAI'}: {message}")
            return "AI settings saved."
        if key == "notifications":
            prefs.save(store, {k: bool(form.get(k)) for k in ("notify_digest", "notify_morning", "notify_eod",
                                                              "notify_weekly", "notify_monthly", "notify_qa",
                                                              "auto_draft_followups")}, me["id"])
            return "Notification choices saved."
        if key == "scheduler":
            for k in ("morning_brief", "weekly_time"):
                v = form.get(k) or ""
                if v and not re.fullmatch(r"\d{1,2}:\d{2}", v):
                    raise ValueError("Times look like 08:30.")
            prefs.save(store, {"morning_brief": form.get("morning_brief") or "", "weekly_day": form.get("weekly_day") or "",
                               "weekly_time": form.get("weekly_time") or ""}, me["id"])
            return "Saved. New times apply after the console restarts."
        if key == "security":
            safe = bool(form.get("safe_mode"))
            if not safe and form.get("confirm") != "TURN OFF":
                raise ValueError('To turn Safe Mode off, type TURN OFF in the box. Outgoing messages would then '
                                 'go out without approval when trusted.')
            prefs.save(store, {"safe_mode": safe, "trust_followups": bool(form.get("trust_followups")),
                               "trust_whatsapp_replies": bool(form.get("trust_whatsapp_replies"))}, me["id"])
            return "Safe Mode is on: outgoing messages wait for your approval." if safe else \
                "Safe Mode is off. Only the kinds you trusted are sent automatically."
        if key in ("email", "whatsapp", "calendar", "drive"):
            if key == "email" and form.get("address"):
                integ.detect_email(store, settings, form["address"], me["id"])
            values = {f.key: (form.get(f.key) or "").strip() for f in integ.BY_NAME[key].fields
                      if f.key in form and not integ.from_env(settings, f.key)}
            if key == "whatsapp" and values.get("WHATSAPP_RECIPIENT"):
                values["WHATSAPP_RECIPIENT"] = re.sub(r"\D", "", values["WHATSAPP_RECIPIENT"])
            if key == "whatsapp" and not integ.with_integrations(settings, store).secret("WHATSAPP_VERIFY_TOKEN"):
                values["WHATSAPP_VERIFY_TOKEN"] = integ.new_verify_token()
            if any(values.values()):
                integ.save_values(store, settings, key, values, me["id"])
                if integ.is_configured(key, integ.with_integrations(settings, store)):
                    ok, message = integ.run_check(key, settings, store)
                    if not ok:
                        raise ValueError(f"{integ.BY_NAME[key].title}: {message}")
            return ""
        if key == "backup":
            from .pa import backup
            path = backup.make(store, settings)
            return f"Backup saved: {path.name}" if path else "Backups need the database on disk."
        if key == "phone":
            on = bool(form.get("lan_access"))
            prefs.save(store, {"lan_access": on}, me["id"])
            return ("Phone access is on. Restart NeuraNova PA once, then open the address below on your phone "
                    "(same Wi-Fi)." if on else "Phone access is off after the next restart.")
        if key == "review":
            return ""
        raise ValueError("Unknown settings section.")

    def _settings_view(agent) -> dict:
        s = prefs.apply(settings, agent.store)
        wh = s.working_hours
        return {"timezone": s.tz.key, "work_start": wh.start.strftime("%H:%M"), "work_end": wh.end.strftime("%H:%M"),
                "work_days": [["mon", "tue", "wed", "thu", "fri", "sat", "sun"][d] for d in sorted(wh.days)],
                "reply_hours": f"{s.sla_hours:g}", "morning_brief": s.morning_brief.strftime("%H:%M"),
                "weekly_day": s.weekly_report_day, "weekly_time": s.weekly_report_time.strftime("%H:%M"),
                "company_name": s.brand.get("name", "NeuraNova")}


# --- helpers ---------------------------------------------------------------------------------------------------

LABELS = {"repeats": recurring.CHOICES, "kinds": KINDS, "statuses": STATUS_LABELS, "priorities": PRIORITIES, "departments": DEPARTMENTS,
          "lead_stages": LEAD_STAGE_LABELS, "qa_stages": QA_STAGE_LABELS, "quality": QUALITY_CATEGORIES,
          "focus": dict(briefing.FOCUS)}


def _event_kinds():
    from .progress import EVENT_KINDS
    return EVENT_KINDS


def _actor(agent, actor: str) -> str:
    if actor in ("PA", "QA", "agent", "system") or actor.startswith("PA"):
        return "NeuraNova PA" if actor != "QA" else "QA checks"
    user = agent.store.user(actor)
    return user["name"] if user else actor


FIELD_NAMES = {"due_at": "Due", "owner_id": "Owner", "status": "Status", "priority": "Priority", "title": "Title",
               "stage": "Stage", "department": "Department", "description": "Details", "waiting_on": "Waiting on",
               "related_person": "Person", "related_project": "Project", "next_action": "Next action", "value": "Value",
               "follow_up_at": "Follow up", "kind": "Type", "verification": "Check"}
SOURCES = {"manual": "added by hand", "email": "from an email", "whatsapp": "from WhatsApp", "qa": "found by QA checks",
           "calendar": "from a meeting", "chat": "from the AI Assistant"}


def _when_text(value) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%a %d %b %H:%M")
    except ValueError:
        return str(value)[:16]


def _event_text(e, agent=None) -> str:
    if e["event"] == "note":
        return e["detail"]
    try:
        data = json.loads(e["detail"] or "{}")
    except ValueError:
        return e["detail"]
    if not isinstance(data, dict):
        return str(data)
    if e["event"] == "created":
        what = KINDS.get(data.get("kind", ""), "Item")
        src = SOURCES.get(data.get("source", ""), "")
        return f"Added as {what}" + (f" ({src})" if src else "")
    parts = []
    for k, v in data.items():
        if k in ("data", "fingerprint", "updated_at", "reminded", "overdue_alerted", "completed_at", "waiting_since"):
            continue
        name = FIELD_NAMES.get(k, k.replace("_", " ").capitalize())
        if k == "status":
            v = STATUS_LABELS.get(v, v)
        elif k == "stage":
            v = LEAD_STAGE_LABELS.get(v) or QA_STAGE_LABELS.get(v, v)
        elif k == "owner_id":
            user = agent.store.user(v) if (agent and v) else None
            v = user["name"] if user else ("nobody" if not v else v)
        elif k in ("due_at", "follow_up_at"):
            v = _when_text(v) if v else "none"
        parts.append(f"{name} → {v}")
    return "; ".join(parts) or e["event"].replace("_", " ")


def _audit_detail(detail: str) -> str:
    try:
        data = json.loads(detail)
    except ValueError:
        return detail[:200]
    return ", ".join(f"{k}: {v}" for k, v in data.items() if k not in ("text",))[:200]


def _evidence(row) -> dict | None:
    if row["kind"] != "qa_issue":
        return None
    data = data_of(row)
    ev = data.get("last_evidence")
    if not ev:
        return None
    shot = ev.get("screenshot") or ""
    m = re.search(r"run-(\d+)[\\/]+([a-z0-9-]+\.png)$", shot)
    return {**ev, "occurrences": data.get("occurrences", 1),
            "screenshot_url": f"/qa/evidence/{m.group(1)}/{m.group(2)}" if m else ""}


def _same_site(referer: str, fallback: str) -> str:
    """The page the person was on (path only), so quick actions return there."""
    from urllib.parse import urlparse
    u = urlparse(referer or "")
    path = (u.path or "") + (f"?{u.query}" if u.query else "")
    path = re.sub(r"[?&]msg=[^&]*", "", path).replace("?&", "?").rstrip("?")
    return path if path.startswith("/") and not path.startswith("//") and path != "/login" else fallback


def _lan_ip() -> str:
    """This computer's address on the local network (no traffic is sent)."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            ip = sock.getsockname()[0]
        return "" if ip.startswith("127.") else ip
    except OSError:
        return ""


def _cell(value) -> str:
    """Spreadsheet safety: text starting with = + - @ is shown as text, never run as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text
