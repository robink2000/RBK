"""Progress against NeuraNova's three goals, computed from email history and logged events.

- Develop the business: new leads (from email triage) plus logged meetings, proposals and deals.
- Give proper responses: share of client/lead/partner emails answered within the reply promise.
- Deliver high quality: deliveries on time vs late, rework, client feedback.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from statistics import median

from .db import Store, row_dt

EVENT_KINDS = {
    "meeting": "Meeting / call with a client or lead",
    "proposal_sent": "Proposal or quote sent",
    "deal_won": "Deal won (value = amount)",
    "deal_lost": "Deal lost",
    "delivery_on_time": "Work delivered on time",
    "delivery_late": "Work delivered late",
    "rework": "Rework / fix requested by a client",
    "feedback_positive": "Positive client feedback",
    "feedback_negative": "Negative client feedback",
    "note": "Other milestone",
}

# Status thresholds for percentages (good >= first, warning >= second, else critical)
THRESHOLDS = (90, 70)


def _pct(part: int, whole: int) -> int | None:
    return round(100 * part / whole) if whole else None


def status_for(pct: int | None) -> str:
    if pct is None:
        return "none"
    return "good" if pct >= THRESHOLDS[0] else "warning" if pct >= THRESHOLDS[1] else "critical"


def compute(store: Store, tz, days: int = 7, now: datetime | None = None) -> dict:
    """Numbers for the last `days` days (ending now)."""
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    start_date = start.astimezone(tz).date().isoformat()
    end_date = (now.astimezone(tz).date() + timedelta(days=1)).isoformat()

    emails = store.emails_between(start, now)
    leads = {r["sender"].lower() for r in emails if r["category"] == "lead"}
    events = store.events_between(start_date, end_date)
    count = {k: 0 for k in EVENT_KINDS}
    won_value = 0.0
    for e in events:
        count[e["kind"]] = count.get(e["kind"], 0) + 1
        if e["kind"] == "deal_won" and e["value"]:
            won_value += e["value"]

    held = [r for r in emails if r["reply_deadline"]]
    on_time = late = overdue = open_ = 0
    reply_hours = []
    for r in held:
        deadline, replied = row_dt(r["reply_deadline"]), row_dt(r["replied_at"])
        if replied:
            reply_hours.append((replied - row_dt(r["received_at"])).total_seconds() / 3600)
            if replied <= deadline:
                on_time += 1
            else:
                late += 1
        elif now > deadline:
            overdue += 1
        else:
            open_ += 1
    response_pct = _pct(on_time, on_time + late + overdue)

    deliveries = count["delivery_on_time"] + count["delivery_late"]
    delivery_pct = _pct(count["delivery_on_time"], deliveries)
    decided = count["deal_won"] + count["deal_lost"]

    return {
        "days": days,
        "business": {
            "new_leads": len(leads),
            "meetings": count["meeting"],
            "proposals_sent": count["proposal_sent"],
            "deals_won": count["deal_won"],
            "deals_lost": count["deal_lost"],
            "won_value": won_value,
            "win_rate_pct": _pct(count["deal_won"], decided),
            "status": "good" if count["deal_won"] or count["proposal_sent"] else "warning" if leads or count["meeting"] else "critical",
        },
        "responses": {
            "on_time": on_time, "late": late, "overdue_now": overdue, "open": open_,
            "on_time_pct": response_pct,
            "median_reply_hours": round(median(reply_hours), 1) if reply_hours else None,
            "status": status_for(response_pct),
        },
        "quality": {
            "deliveries_on_time": count["delivery_on_time"],
            "deliveries_late": count["delivery_late"],
            "on_time_pct": delivery_pct,
            "rework": count["rework"],
            "feedback_positive": count["feedback_positive"],
            "feedback_negative": count["feedback_negative"],
            "status": "critical" if count["feedback_negative"] > count["feedback_positive"]
                      else status_for(delivery_pct) if deliveries else "none",
        },
    }


def weekly_series(store: Store, tz, weeks: int = 8, now: datetime | None = None) -> list[dict]:
    """Per calendar week (Monday start): new leads, replies on time %, deals won."""
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(tz).date()
    this_monday = today - timedelta(days=today.weekday())
    out = []
    for i in range(weeks - 1, -1, -1):
        monday: date = this_monday - timedelta(weeks=i)
        start = datetime.combine(monday, datetime.min.time(), tz)
        end = min(start + timedelta(days=7), now)
        emails = store.emails_between(start, end)
        held = [r for r in emails if r["reply_deadline"]]
        due = [r for r in held if r["replied_at"] or row_dt(r["reply_deadline"]) < now]
        ok = sum(1 for r in due if r["replied_at"] and row_dt(r["replied_at"]) <= row_dt(r["reply_deadline"]))
        events = store.events_between(monday.isoformat(), (monday + timedelta(days=7)).isoformat())
        out.append({
            "week": monday.isoformat(),
            "label": monday.strftime("%d %b"),
            "new_leads": len({r["sender"].lower() for r in emails if r["category"] == "lead"}),
            "replies_due": len(due),
            "on_time_pct": _pct(ok, len(due)),
            "deals_won": sum(1 for e in events if e["kind"] == "deal_won"),
        })
    return out
