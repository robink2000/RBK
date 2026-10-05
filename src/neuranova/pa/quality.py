"""Quality improvement: open concerns, and the recurring patterns management should look at."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..db import row_dt
from .store import QUALITY_CATEGORIES, PAStore, data_of

WINDOW_DAYS = 14
PATTERN_MIN = 3


def category_of(row) -> str:
    if row["kind"] == "qa_issue":
        return "Application"
    return data_of(row).get("category") or "Uncategorised"


def patterns(pa: PAStore, now: datetime | None = None, days: int = WINDOW_DAYS, minimum: int = PATTERN_MIN) -> list[dict]:
    """Categories with `minimum`+ concerns raised in the last `days` days, worst first."""
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    counts: dict[str, list] = {}
    for row in pa.items_created_between(start, now + timedelta(seconds=1)):
        if row["kind"] not in ("quality", "qa_issue"):
            continue
        counts.setdefault(category_of(row), []).append(row)
    out = []
    for category, rows in counts.items():
        if len(rows) >= minimum:
            out.append({"category": category, "count": len(rows), "days": days,
                        "open": sum(1 for r in rows if r["status"] != "closed"),
                        "examples": [r["title"] for r in rows[:3]],
                        "text": f"Recurring issue: {category} — {len(rows)} related concerns in {days} days. "
                                f"Management attention recommended."})
    return sorted(out, key=lambda p: -p["count"])


def summary(pa: PAStore, days: int = 30, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    open_rows = pa.items(kind="quality", status="active", limit=1000)
    raised = [r for r in pa.items_created_between(start, now + timedelta(seconds=1)) if r["kind"] == "quality"]
    by_category = {c: 0 for c in QUALITY_CATEGORIES}
    for r in raised:
        c = category_of(r)
        by_category[c] = by_category.get(c, 0) + 1
    resolved = [r for r in pa.items_completed_between(start, now + timedelta(seconds=1)) if r["kind"] == "quality"]
    durations = [(row_dt(r["completed_at"]) - row_dt(r["created_at"])).total_seconds() / 86400 for r in resolved]
    return {
        "days": days, "open": open_rows, "raised": len(raised), "resolved": len(resolved),
        "by_category": {k: v for k, v in by_category.items() if v},
        "avg_days_to_resolve": round(sum(durations) / len(durations), 1) if durations else None,
        "patterns": patterns(pa, now),
    }
