"""Proactive PA: surface what matters without being asked, without spamming.

Rules:
- one digest message per run, at most MAX_LINES lines (the rest: "and N more")
- each matter is mentioned once (keys stored in reminders_sent)
- at most one digest per MIN_GAP unless something is urgent
- outside working hours only urgent matters go out; the rest wait for the morning
- items with an owner are handled by the owner reminders (jobs.team_reminders), not repeated here
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..db import row_dt
from . import business, quality

MAX_LINES = 8
MIN_GAP = timedelta(minutes=60)
UNANSWERED_AFTER = timedelta(hours=2)
RETEST_AFTER = timedelta(hours=24)
DECISION_AFTER = timedelta(hours=24)


def _in_hours(now: datetime, hours) -> bool:
    return now.weekday() in hours.days and hours.start <= now.time() < hours.end


def candidates(store, settings, now: datetime) -> list[dict]:
    pa = store.pa
    out: list[dict] = []

    def add(key: str, text: str, urgent: bool = False, score: int = 50) -> None:
        out.append({"key": key, "text": text, "urgent": urgent, "score": score})

    for row in pa.items(status="active", limit=2000):
        due = row_dt(row["due_at"]) if row["due_at"] else None
        if row["owner_id"]:
            continue
        if due and due < now:
            stamp = row["due_at"]
            if row["kind"] == "waiting":
                who = row["waiting_on"] or row["related_person"] or "Someone"
                add(f"item:{row['id']}:late:{stamp}", f"⏳ {who} hasn't delivered: {row['title']} "
                    f"(expected {due.astimezone(settings.tz):%a %H:%M})", score=70)
            else:
                add(f"item:{row['id']}:late:{stamp}", f"⚠️ Overdue: {row['title']}",
                    urgent=row["priority"] == "urgent", score=80 if row["priority"] in ("urgent", "high") else 60)
        elif due and due - now <= timedelta(hours=2) and row["priority"] in ("urgent", "high"):
            add(f"item:{row['id']}:soon:{row['due_at']}",
                f"⏰ Due {due.astimezone(settings.tz):%H:%M}: {row['title']}", urgent=row["priority"] == "urgent",
                score=75)
        if row["kind"] == "decision" and now - row_dt(row["created_at"]) > DECISION_AFTER:
            add(f"decision:{row['id']}:{now:%Y-%m-%d}", f"🧭 Decision waiting: {row['title']}", score=65)
        if row["status"] == "ready_for_retest" and now - row_dt(row["updated_at"]) > RETEST_AFTER:
            add(f"retest:{row['id']}", f"🔁 Fix waiting for retest: {row['title']}", score=55)

    for m in pa.awaiting_our_reply(now - UNANSWERED_AFTER):
        who = m["contact_name"] or m["sender"]
        add(f"wa:{m['id']}", f"💬 {who} is waiting for a reply on WhatsApp: {m['summary'] or m['body'][:80]}",
            urgent=m["importance"] == "high", score=78 if m["importance"] == "high" else 58)

    biz = business.pipeline(pa, now=now)
    for row in biz["hot"]:
        add(f"lead:{row['id']}:hot", f"🔥 Hot lead: {row['title']}", score=72)
    for row in biz["stalled"]:
        add(f"lead:{row['id']}:stalled:{now.isocalendar().year}-W{now.isocalendar().week}", f"🧊 Stalled lead (5+ days quiet): {row['title']}",
            score=45)
    for p in quality.patterns(pa, now):
        add(f"pattern:{p['category']}:{now.isocalendar().year}-W{now.isocalendar().week}", f"📈 {p['text']}", score=68)
    return sorted(out, key=lambda c: -c["score"])


def run(store, settings, notify, now: datetime | None = None) -> dict:
    now = (now or datetime.now(timezone.utc)).astimezone(settings.tz)
    in_hours = _in_hours(now, settings.working_hours)
    fresh = [c for c in candidates(store, settings, now)
             if not store.reminder_sent_check(c["key"]) and (in_hours or c["urgent"])]
    if not fresh:
        return {"sent": 0, "pending": 0}
    last = store.get("pa_last_digest")
    urgent = any(c["urgent"] for c in fresh)
    if last and not urgent and now - datetime.fromisoformat(last) < MIN_GAP:
        return {"sent": 0, "pending": len(fresh)}
    shown = fresh[:MAX_LINES]
    lines = ["NeuraNova PA · needs your attention", *[f"- {c['text']}" for c in shown]]
    if len(fresh) > MAX_LINES:
        lines.append(f"…and {len(fresh) - MAX_LINES} more. Open the PA for the full list.")
    notify("\n".join(lines), teaser=f"NeuraNova PA: {len(fresh)} matter{'s' * (len(fresh) > 1)} need your attention.")
    for c in fresh:  # everything in the digest (shown or summarised) counts as mentioned
        store.reminder_sent(c["key"], "pa")
    store.put("pa_last_digest", now.isoformat())
    store.log("pa_digest", items=len(fresh))
    return {"sent": len(fresh), "pending": 0}
