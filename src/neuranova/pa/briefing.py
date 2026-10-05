"""The PA briefing: "what needs attention now, and what should management do next?"

Computed directly from stored data (no AI call), so the home page is instant and always current.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..connectors.gmail import sender_name
from ..db import row_dt
from . import business, quality
from .dates import bucket
from .store import KINDS, PRIORITY_RANK, STATUS_LABELS, PAStore, data_of

FOCUS = [
    ("urgent", "Urgent"), ("overdue", "Overdue"), ("due_today", "Due today"), ("waiting_reply", "Waiting for your reply"),
    ("waiting_others", "Waiting on others"), ("follow_ups", "Follow-ups"), ("meetings", "Meetings"),
    ("opportunities", "Business opportunities"), ("app_issues", "Application issues"),
    ("quality", "Quality concerns"), ("decisions", "Decisions required"),
]


def _when(dt: datetime | None, now: datetime) -> str:
    if dt is None:
        return ""
    local, today = dt.astimezone(now.tzinfo), now.date()
    if local.date() == today:
        return local.strftime("today %H:%M")
    if local.date() == today + timedelta(days=1):
        return local.strftime("tomorrow %H:%M")
    if local.date() == today - timedelta(days=1):
        return local.strftime("yesterday %H:%M")
    if abs((local.date() - today).days) < 7:
        return local.strftime("%a %H:%M")
    return local.strftime("%d %b")


def _ago(dt: datetime, now: datetime) -> str:
    hours = (now - dt).total_seconds() / 3600
    if hours < 1:
        return f"{int(hours * 60)} min"
    if hours < 48:
        return f"{int(hours)} h"
    return f"{int(hours // 24)} days"


def entry(row, now: datetime, signals: list[str] | None = None) -> dict:
    due = row_dt(row["due_at"]) if row["due_at"] else None
    data = data_of(row)
    return {
        "id": row["id"], "kind": row["kind"], "kind_label": KINDS.get(row["kind"], row["kind"]),
        "title": row["title"], "owner": row["owner_name"] or "", "priority": row["priority"],
        "status": STATUS_LABELS.get(row["status"], row["status"]), "stage": row["stage"],
        "due": _when(due, now), "overdue": bool(due and due < now), "bucket": bucket(due, now),
        "who": row["waiting_on"] or row["related_person"] or row["contact_name"] or "",
        "next_action": row["next_action"] or data.get("blocked_reason", ""), "source": row["source"],
        "link": f"/tasks/{row['id']}", "signals": signals or [],
    }


def build(store, settings, now: datetime | None = None, meetings: list[dict] | None = None,
          user_name: str = "") -> dict:
    pa: PAStore = store.pa
    tz = settings.tz
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    items = pa.items(status="active", limit=2000)
    focus: dict[str, list] = {key: [] for key, _ in FOCUS}
    actions: list[dict] = []

    def act(score: float, text: str, why: str, link: str) -> None:
        actions.append({"score": score, "text": text, "why": why, "link": link})

    biz = business.pipeline(pa, now=now)
    lead_flags = biz["signals"]

    for row in items:
        e = entry(row, now, lead_flags.get(row["id"]))
        due = row_dt(row["due_at"]) if row["due_at"] else None
        kind = row["kind"]
        weight = 10 if kind in ("lead", "payment") else 0
        if row["priority"] == "urgent":
            focus["urgent"].append(e)
            act(95 + weight, f"Handle: {row['title']}", "Marked urgent" + (f", due {e['due']}" if e["due"] else ""),
                e["link"])
        if kind == "waiting" or row["status"] == "waiting":
            focus["waiting_others"].append(e)
            if due and due < now:
                who = row["waiting_on"] or row["related_person"] or "them"
                act(72 + weight, f"Follow up with {who}: {row['title']}",
                    f"Expected {e['due']}, not received", e["link"])
            continue
        if kind == "decision":
            focus["decisions"].append(e)
            act(78, f"Decide: {row['title']}", "Waiting for a management decision", e["link"])
        elif kind == "qa_issue":
            focus["app_issues"].append(e)
            if row["status"] == "ready_for_retest":
                act(60, f"Retest: {row['title']}", "Developer marked it fixed; QA retest pending", e["link"])
        elif kind == "quality":
            focus["quality"].append(e)
        elif kind == "lead":
            if {"hot", "follow_up_due", "payment_pending"} & set(e["signals"]):
                focus["opportunities"].append(e)
            if "hot" in e["signals"]:
                act(74, f"Contact {e['who'] or 'lead'}: {row['title']}", "Hot lead, active in the last 3 days",
                    e["link"])
            elif "stalled" in e["signals"]:
                act(55, f"Revive stalled lead: {row['title']}", "No activity for 5+ days", e["link"])
        elif kind == "follow_up":
            focus["follow_ups"].append(e)
        if due and due < now and row["priority"] != "urgent":
            focus["overdue"].append(e)
            days = (now - due).total_seconds() / 86400
            act(80 + min(days * 5, 15) + weight, f"Overdue: {row['title']}",
                f"Was due {e['due']}" + (f" · {e['owner']}" if e["owner"] else " · no owner"), e["link"])
        elif due and e["bucket"] == "today":
            focus["due_today"].append(e)
            act(66 + weight, f"Due today: {row['title']}", f"Due {e['due']}" + (f" · {e['owner']}" if e["owner"] else ""),
                e["link"])
        follow = row_dt(row["follow_up_at"]) if row["follow_up_at"] else None
        if follow and follow <= now + timedelta(hours=2) and kind != "follow_up":
            focus["follow_ups"].append(e)

    # emails you owe a reply (the 4-hour promise)
    for r in store.awaiting_reply():
        deadline = row_dt(r["reply_deadline"]) if r["reply_deadline"] else None
        late = bool(deadline and deadline < now)
        focus["waiting_reply"].append({
            "id": r["id"], "kind": "email", "kind_label": "Email", "title": r["subject"],
            "who": sender_name(r["sender"]), "due": _when(deadline, now), "overdue": late,
            "next_action": r["suggested_action"] or "", "link": "/communications#email", "owner": "",
            "priority": r["priority"] or "medium", "status": "", "stage": "", "source": "email", "signals": []})
        if late:
            act(100 + min((now - deadline).total_seconds() / 3600, 20), f"Reply to {sender_name(r['sender'])}",
                f"\"{r['subject']}\" · reply was due {_when(deadline, now)}", "/communications#email")
    # WhatsApp messages from contacts nobody answered
    for m in pa.awaiting_our_reply(now - timedelta(hours=2)):
        at = row_dt(m["at"])
        focus["waiting_reply"].append({
            "id": m["id"], "kind": "whatsapp", "kind_label": "WhatsApp", "title": m["summary"] or m["body"][:80],
            "who": m["contact_name"] or m["sender"], "due": f"{_ago(at, now)} ago", "overdue": True,
            "next_action": "", "link": "/communications#whatsapp", "owner": "", "priority": m["importance"],
            "status": "", "stage": "", "source": "whatsapp", "signals": []})
        act(82 if m["importance"] == "high" else 64, f"Reply on WhatsApp to {m['contact_name'] or m['sender']}",
            f"Waiting {_ago(at, now)}", "/communications#whatsapp")

    for m in meetings or []:
        focus["meetings"].append(m)
        if m.get("prep"):
            act(70, f"Prepare for {m['title']} ({m['when']})", f"{len(m['prep'])} related open items", "/today#meetings")

    patterns = quality.patterns(pa, now)
    for p in patterns:
        act(68, f"Look into recurring {p['category']} issues", f"{p['count']} concerns in {p['days']} days", "/quality")

    drafts = store.pending_drafts()
    if drafts:
        act(85, f"Approve {len(drafts)} reply draft{'s' * (len(drafts) > 1)}", "Ready to send once you approve",
            "/#drafts")
    outbox = pa.outbox("pending")
    if outbox:
        act(84, f"Approve {len(outbox)} outgoing message{'s' * (len(outbox) > 1)}", "Safe Mode is holding them for you",
            "/communications#approvals")
    unowned = [r for r in items if not r["owner_id"] and r["kind"] in ("task", "qa_issue", "follow_up", "decision")]
    if unowned:
        act(50, f"Assign owners to {len(unowned)} item{'s' * (len(unowned) > 1)}", "Nobody is responsible yet",
            "/tasks?owner=__none__")

    for key in focus:
        focus[key].sort(key=lambda e: (not e.get("overdue"), PRIORITY_RANK.get(e.get("priority") or "medium", 2)))

    waiting_late = [e for e in focus["waiting_others"] if e["overdue"]]
    payments = [r for r in items if r["kind"] == "payment" or (r["kind"] == "lead" and r["stage"] == "payment_pending")]
    retest = [e for e in focus["app_issues"] if e["status"] == STATUS_LABELS["ready_for_retest"]]
    headline = [
        (len(focus["urgent"]), "urgent item", "urgent"),
        (len(focus["overdue"]), "overdue item", "overdue"),
        (len(focus["due_today"]), "due today", "due_today"),
        (len(focus["waiting_reply"]), "waiting for your reply", "waiting_reply"),
        (len(waiting_late), "person has not delivered as promised", "waiting_others"),
        (len(focus["follow_ups"]), "follow-up due", "follow_ups"),
        (len(payments), "payment matter open", "opportunities"),
        (len(biz["hot"]) + len(biz["follow_ups_due"]), "lead needs attention", "opportunities"),
        (len(retest), "application fix needs retesting", "app_issues"),
        (len(patterns), "recurring quality issue", "quality"),
        (len(focus["decisions"]), "management decision pending", "decisions"),
        (len(meetings or []), "meeting today", "meetings"),
    ]
    plural = {"person has not delivered as promised": "people have not delivered as promised",
              "due today": "due today", "waiting for your reply": "waiting for your reply"}
    lines = [{"count": n, "text": (plural.get(t, t + "s") if n != 1 else t), "anchor": a}
             for n, t, a in headline if n]

    hour = now.hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    actions.sort(key=lambda a: -a["score"])
    seen, top = set(), []
    for a in actions:
        if a["text"] not in seen:
            seen.add(a["text"])
            top.append(a)
    return {
        "greeting": f"{greeting}{', ' + user_name.split()[0] if user_name else ''}",
        "date": now.strftime("%A %d %B %Y"), "headline": lines, "focus": focus,
        "focus_labels": FOCUS, "actions": top[:8], "all_clear": not lines and not top,
        "business": biz, "patterns": patterns,
        "counts": {k: len(v) for k, v in focus.items()},
    }
