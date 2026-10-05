"""Preferences set in the browser (Settings): company, hours, schedules, notifications and security.

They are stored in the database and take precedence over neuranova.toml, so nobody needs to edit
config files. Schedule changes apply the next time the console starts.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..config import DAY_NAMES, WorkingHours

KEY = "pa_prefs"

DEFAULTS = {
    "company_name": "NeuraNova",
    "timezone": "",
    "work_start": "", "work_end": "", "work_days": [],
    "reply_hours": None,
    "morning_brief": "", "weekly_day": "", "weekly_time": "",
    "safe_mode": True,
    # trusted automation: only effective when Safe Mode is off
    "trust_followups": False,      # send polite follow-ups for overdue promises automatically
    "trust_whatsapp_replies": False,
    "notify_digest": True, "notify_morning": True, "notify_eod": True, "notify_weekly": True,
    "notify_monthly": True, "notify_qa": True,
    "auto_draft_followups": True,  # draft follow-ups for overdue promises (they wait for approval)
    "setup_done": False, "setup_step": 1,
}


def get(store) -> dict:
    raw = store.get(KEY)
    data = json.loads(raw) if raw else {}
    return {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}


def save(store, updates: dict, by: str = "") -> dict:
    current = get(store)
    changed = {k: v for k, v in updates.items() if k in DEFAULTS and current.get(k) != v}
    current.update(changed)
    store.put(KEY, json.dumps(current))
    if changed:
        safe = {k: v for k, v in changed.items()}
        store.log("settings_changed", by=by, changed=sorted(safe))
    return current


def _t(value: str, fallback: time) -> time:
    try:
        h, m = value.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return fallback


def apply(settings, store):
    """Settings with browser-saved preferences applied."""
    p = get(store)
    changes: dict = {}
    if p["timezone"]:
        try:
            changes["tz"] = ZoneInfo(p["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            pass
    if p["work_start"] or p["work_end"] or p["work_days"]:
        wh = settings.working_hours
        days = frozenset(DAY_NAMES.index(d) for d in p["work_days"] if d in DAY_NAMES) or wh.days
        start, end = _t(p["work_start"], wh.start), _t(p["work_end"], wh.end)
        if end > start:
            changes["working_hours"] = WorkingHours(start, end, days)
    if p["reply_hours"]:
        changes["sla_hours"] = float(p["reply_hours"])
    if p["morning_brief"]:
        changes["morning_brief"] = _t(p["morning_brief"], settings.morning_brief)
    if p["weekly_day"] in DAY_NAMES:
        changes["weekly_report_day"] = p["weekly_day"]
    if p["weekly_time"]:
        changes["weekly_report_time"] = _t(p["weekly_time"], settings.weekly_report_time)
    if p["company_name"] and settings.brand.get("name") != p["company_name"]:
        changes["brand"] = {**settings.brand, "name": p["company_name"]}
    return replace(settings, **changes) if changes else settings


def safe_mode(store) -> bool:
    return bool(get(store)["safe_mode"])


def may_send_automatically(store, kind: str) -> bool:
    """External sends happen without approval only when Safe Mode is off AND that kind is trusted."""
    p = get(store)
    if p["safe_mode"]:
        return False
    return bool(p.get(f"trust_{kind}"))
