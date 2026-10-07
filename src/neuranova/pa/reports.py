"""Summaries: Morning Brief, End-of-Day, Weekly Management, Monthly Business, Sales, Quality, Application QA.

Facts are gathered from stored data (no AI). The AI only turns the facts into readable text; if it is
unavailable the report is still produced as plain text, so a summary is never lost.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from ..db import row_dt
from . import briefing, business, quality
from .store import KINDS, LEAD_STAGE_LABELS, PAStore, data_of

log = logging.getLogger(__name__)

TITLES = {"morning": "Morning Brief", "eod": "End-of-Day Summary", "weekly": "Weekly Management Summary",
          "monthly": "Monthly Business Summary", "sales": "Sales Summary", "quality": "Quality Summary",
          "qa": "Application QA Summary"}
PERIOD_DAYS = {"morning": 1, "eod": 1, "weekly": 7, "monthly": 30, "sales": 7, "quality": 14, "qa": 7}

WRITER = """You are NeuraNova PA writing the {title} for NeuraNova's management.

Business goals:
{goals}

Write it like a sharp executive assistant: what matters, what changed, what is at risk, what to do next.
- Plain text that reads well on WhatsApp and on screen: short section titles in *bold*, short lines, "- " bullets.
- Lead with what needs action. Name people, numbers and deadlines. No filler, no greetings beyond one line.
- Only use the facts given. If a section has no data, say so in one line or skip it.
- End with 2-4 concrete recommended actions.
- Keep it under {limit} characters."""


def _brief(rows, now, limit=8) -> list[str]:
    out = []
    for r in rows[:limit]:
        due = row_dt(r["due_at"]) if r["due_at"] else None
        bits = [r["title"]]
        if r["owner_name"]:
            bits.append(r["owner_name"])
        if due:
            bits.append(("overdue since " if due < now else "due ") + due.astimezone(now.tzinfo).strftime("%a %d %b %H:%M"))
        out.append(" · ".join(bits))
    return out


def facts(kind: str, store, settings, now: datetime | None = None, meetings: dict | None = None) -> dict:
    pa: PAStore = store.pa
    now = (now or datetime.now(timezone.utc)).astimezone(settings.tz)
    days = PERIOD_DAYS[kind]
    start = now - timedelta(days=days)
    if kind in ("eod", "morning"):        # "today" means the calendar day here, not the last 24 hours
        start = datetime.combine(now.date(), datetime.min.time(), now.tzinfo) - (timedelta(days=1) if kind == "morning" else timedelta())
    b = briefing.build(store, settings, now=now, meetings=(meetings or {}).get("today"))
    biz = business.pipeline(pa, days=max(days, 7), now=now)
    qual = quality.summary(pa, days=max(days, 14), now=now)
    done = pa.items_completed_between(start, now)
    created = pa.items_created_between(start, now)
    active = pa.items(status="active", limit=3000)
    f: dict = {"report": TITLES[kind], "date": now.strftime("%A %d %B %Y"), "period_days": days}

    def section_items(key):
        return [f"{e['title']}" + (f" ({e['who']})" if e.get("who") else "") + (f" · {e['due']}" if e.get("due") else "")
                for e in b["focus"][key][:8]]

    if kind in ("morning", "eod", "weekly", "monthly"):
        f["attention_now"] = [line["text"] if line["count"] == 1 else f"{line['count']} {line['text']}"
                              for line in b["headline"]]
        f["recommended_actions"] = [f"{a['text']} — {a['why']}" for a in b["actions"]]
    if kind == "morning":
        for key, label in briefing.FOCUS:
            if key != "meetings":
                f[label] = section_items(key)
        f["meetings_today"] = [f"{m['when']} {m['title']}" + (f" (prepare: {', '.join(p['title'] for p in m['prep'][:3])})"
                                                              if m["prep"] else "") for m in (meetings or {}).get("today", [])]
    if kind == "eod":
        f["completed_today"] = [f"{r['title']}" + (f" ({r['owner_name']})" if r["owner_name"] else "") for r in done][:15]
        f["still_pending_due_today"] = section_items("due_today")
        f["missed_today"] = section_items("overdue")
        f["new_issues"] = [r["title"] for r in created if r["kind"] in ("qa_issue", "quality")][:10]
        f["new_opportunities"] = [r["title"] for r in created if r["kind"] == "lead"][:10]
        f["waiting_for_replies"] = section_items("waiting_reply") + section_items("waiting_others")
        tomorrow = [r for r in active if r["due_at"] and row_dt(r["due_at"]).astimezone(settings.tz).date()
                    == (now + timedelta(days=1)).date()]
        f["tomorrow_priorities"] = _brief(tomorrow, now)
        f["meetings_tomorrow"] = [f"{m['day']} {m['when']} {m['title']}" for m in (meetings or {}).get("upcoming", [])
                                  if m["start_dt"].date() == (now + timedelta(days=1)).date()]
    if kind in ("weekly", "monthly", "sales"):
        f["business"] = {
            "new_leads": biz["new_leads"], "hot_leads": [r["title"] for r in biz["hot"]][:8],
            "stalled_leads": [r["title"] for r in biz["stalled"]][:8],
            "follow_ups_due": [r["title"] for r in biz["follow_ups_due"]][:8],
            "demos_pending": len(biz["demos_pending"]), "admissions_in_progress": len(biz["in_progress"]),
            "payment_pending": [r["title"] for r in biz["payment_pending"]][:8],
            "converted": len(biz["converted"]), "lost": len(biz["lost"]), "lost_reasons": biz["lost_reasons"],
            "conversion_pct": biz["conversion_pct"], "won_value": biz["won_value"], "pipeline": biz["by_stage"]}
    if kind in ("weekly", "monthly"):
        by_owner: dict[str, dict] = {}
        for r in active:
            o = by_owner.setdefault(r["owner_name"] or "Unassigned", {"open": 0, "overdue": 0, "blocked": 0, "waiting": 0})
            o["open"] += 1
            o["overdue"] += bool(r["due_at"] and row_dt(r["due_at"]) < now)
            o["blocked"] += r["status"] == "blocked"
            o["waiting"] += r["status"] == "waiting"
        for r in done:
            by_owner.setdefault(r["owner_name"] or "Unassigned", {"open": 0, "overdue": 0, "blocked": 0,
                                                                  "waiting": 0}).setdefault("completed", 0)
            by_owner[r["owner_name"] or "Unassigned"]["completed"] = by_owner[r["owner_name"] or "Unassigned"].get("completed", 0) + 1
        f["operations"] = {"completed": len(done), "created": len(created), "open_now": len(active),
                           "overdue_now": len(b["focus"]["overdue"]), "blocked_now": sum(1 for r in active if r["status"] == "blocked"),
                           "by_kind_created": _count(created, lambda r: KINDS.get(r["kind"], r["kind"]))}
        f["team"] = by_owner
        f["critical_risks"] = [e["title"] for e in b["focus"]["urgent"]][:5] + [p["text"] for p in b["patterns"]]
        f["decisions_required"] = section_items("decisions")
        upcoming = [r for r in active if r["due_at"] and now < row_dt(r["due_at"]) <= now + timedelta(days=7)]
        f["next_week_deadlines"] = _brief(upcoming, now, 10)
        from ..progress import compute
        f["replies_within_promise"] = compute(store, settings.tz, days=days, now=now)["responses"]
    if kind in ("weekly", "monthly", "quality"):
        f["quality"] = {"raised": qual["raised"], "resolved": qual["resolved"], "open": len(qual["open"]),
                        "by_category": qual["by_category"], "avg_days_to_resolve": qual["avg_days_to_resolve"],
                        "recurring_patterns": [p["text"] for p in qual["patterns"]],
                        "open_concerns": [r["title"] for r in qual["open"]][:10]}
    if kind in ("weekly", "monthly", "qa"):
        issues = pa.items(kind="qa_issue", status=None, limit=3000)
        open_issues = [r for r in issues if r["status"] not in ("closed", "verified")]
        runs = pa.qa_runs(30)
        recent_runs = [r for r in runs if row_dt(r["started_at"]) >= start]
        f["application"] = {
            "open_issues": len(open_issues),
            "by_stage": _count(open_issues, lambda r: (r["stage"] or "new").replace("_", " ")),
            "awaiting_retest": [r["title"] for r in open_issues if r["status"] == "ready_for_retest"][:8],
            "production_issues": [r["title"] for r in open_issues if data_of(r).get("environment") == "production"][:8],
            "verified_this_period": sum(1 for r in issues if r["status"] == "verified" and row_dt(r["updated_at"]) >= start),
            "checks_run": len(recent_runs),
            "checks_failed": sum(1 for r in recent_runs if r["status"] == "failed"),
        }
    return f


def _count(rows, key) -> dict:
    out: dict = {}
    for r in rows:
        k = key(r)
        out[k] = out.get(k, 0) + 1
    return out


def plain_text(f: dict) -> str:
    """Readable fallback without AI."""
    lines = [f"*{f['report']}* · {f['date']}"]
    for key, value in f.items():
        if key in ("report", "date", "period_days") or value in (None, [], {}, ""):
            continue
        title = key.replace("_", " ").capitalize()
        if isinstance(value, list):
            lines.append(f"\n*{title}*")
            lines += [f"- {v}" for v in value[:10]]
        elif isinstance(value, dict):
            lines.append(f"\n*{title}*")
            for k, v in value.items():
                if v in (None, [], {}, ""):
                    continue
                if isinstance(v, list):
                    v = "; ".join(map(str, v[:6]))
                elif isinstance(v, dict):
                    v = ", ".join(f"{a}: {b}" for a, b in v.items())
                lines.append(f"- {k.replace('_', ' ')}: {v}")
        else:
            lines.append(f"- {title}: {value}")
    return "\n".join(lines)


def generate(kind: str, store, settings, llm=None, goals: str = "", meetings: dict | None = None,
             now: datetime | None = None) -> dict:
    """Build, write and save a report. Returns {"id", "title", "text", "ai": bool}."""
    if kind not in TITLES:
        raise ValueError(f"Unknown report {kind}")
    now = (now or datetime.now(timezone.utc)).astimezone(settings.tz)
    f = facts(kind, store, settings, now=now, meetings=meetings)
    text, used_ai = None, False
    if llm is not None:
        try:
            limit = 1500 if kind in ("morning", "eod") else 2500
            text = llm.text(WRITER.format(title=TITLES[kind], goals=goals, limit=limit),
                            "Facts:\n" + json.dumps(f, default=str, indent=1), effort="medium", max_tokens=6000)
            used_ai = bool(text)
        except Exception:
            log.exception("AI could not write the %s; using the plain version", kind)
    text = text or plain_text(f)
    title = f"{TITLES[kind]} · {now:%d %b %Y}"
    report_id = store.pa.add_report(kind, title, text, f, now - timedelta(days=PERIOD_DAYS[kind]), now)
    store.log("report", kind=kind, ai=used_ai)
    return {"id": report_id, "title": title, "text": text, "ai": used_ai}


STAGE_ORDER = list(LEAD_STAGE_LABELS)
