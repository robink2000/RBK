"""Business growth: the lead pipeline and the signals that need attention.

Signals come from real activity only (stage, last update, contact activity, due dates), never from
guesses: a lead is "hot" when it is high priority and active in the last 3 days, "stalled" when
nothing has happened for 5+ days, and so on.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..db import row_dt
from .store import LEAD_STAGE_LABELS, LEAD_STAGES, PAStore, data_of

HOT_DAYS = 3
STALLED_DAYS = 5
OPEN_STAGES = ("new", "contacted", "demo_pending", "in_progress", "quoted", "payment_pending")


def _age_days(row, now: datetime) -> float:
    updated = row_dt(row["updated_at"]) or row_dt(row["created_at"])
    return (now - updated).total_seconds() / 86400


def lead_signals(row, now: datetime) -> list[str]:
    stage = row["stage"] or "new"
    signals = []
    if stage not in OPEN_STAGES:
        return signals
    age = _age_days(row, now)
    if row["priority"] in ("urgent", "high") and age <= HOT_DAYS:
        signals.append("hot")
    if age >= STALLED_DAYS:
        signals.append("stalled")
    due = row_dt(row["due_at"]) if row["due_at"] else None
    follow = row_dt(row["follow_up_at"]) if row["follow_up_at"] else None
    if (due and due <= now + timedelta(hours=24)) or (follow and follow <= now + timedelta(hours=24)):
        signals.append("follow_up_due")
    if stage == "payment_pending":
        signals.append("payment_pending")
    if stage == "demo_pending":
        signals.append("demo_pending")
    if age >= STALLED_DAYS * 2 and stage in ("contacted", "quoted"):
        signals.append("at_risk")
    return signals


def pipeline(pa: PAStore, days: int = 30, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    leads = pa.items(kind="lead", status=None, limit=5000)
    by_stage = {s: 0 for s in LEAD_STAGES}
    for row in leads:
        if row["status"] != "closed" or row["stage"] in ("converted", "lost"):
            by_stage[row["stage"] or "new"] = by_stage.get(row["stage"] or "new", 0) + 1
    recent = [r for r in leads if row_dt(r["created_at"]) >= start]
    converted = [r for r in leads if r["stage"] == "converted" and r["updated_at"] and row_dt(r["updated_at"]) >= start]
    lost = [r for r in leads if r["stage"] == "lost" and row_dt(r["updated_at"]) >= start]
    active = [r for r in leads if (r["stage"] or "new") in OPEN_STAGES and r["status"] != "closed"]
    flagged = {r["id"]: lead_signals(r, now) for r in active}
    reasons: dict[str, int] = {}
    for r in lost:
        reason = data_of(r).get("lost_reason") or "Not recorded"
        reasons[reason] = reasons.get(reason, 0) + 1
    decided = len(converted) + len(lost)
    payments = pa.items(kind="payment", status="active", limit=500)
    return {
        "days": days,
        "new_leads": len(recent),
        "hot": [r for r in active if "hot" in flagged[r["id"]]],
        "stalled": [r for r in active if "stalled" in flagged[r["id"]]],
        "follow_ups_due": [r for r in active if "follow_up_due" in flagged[r["id"]]],
        "demos_pending": [r for r in active if r["stage"] == "demo_pending"],
        "in_progress": [r for r in active if r["stage"] in ("in_progress", "quoted")],
        "payment_pending": [r for r in active if r["stage"] == "payment_pending"] + list(payments),
        "no_response": [r for r in leads if r["stage"] == "no_response" and r["status"] != "closed"],
        "converted": converted,
        "lost": lost,
        "lost_reasons": reasons,
        "conversion_pct": round(100 * len(converted) / decided) if decided else None,
        "won_value": sum(r["value"] or 0 for r in converted),
        "by_stage": {LEAD_STAGE_LABELS[s]: n for s, n in by_stage.items()},
        "signals": flagged,
    }
