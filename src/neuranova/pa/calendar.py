"""Calendar: meetings today and coming up, what to prepare, and capturing actions afterwards.

Reads one or more private iCal addresses (Google Calendar: Settings → your calendar → "Secret address in
iCal format"; Outlook: Settings → Calendar → Shared calendars → Publish → ICS). Read-only, no sign-in
needed. Fetched calendars are cached for a few minutes so pages stay fast.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone

import httpx

from .store import PAStore, norm, similarity

log = logging.getLogger(__name__)

CACHE_MINUTES = 10
CAPTURED_KEY = "meeting_captured"


def _events_from_ics(text: str, start: datetime, end: datetime) -> list[dict]:
    import icalendar
    import recurring_ical_events

    cal = icalendar.Calendar.from_ical(text)
    out = []
    for ev in recurring_ical_events.of(cal, skip_bad_series=True).between(start, end):
        dtstart = ev.get("DTSTART").dt
        dtend = ev.get("DTEND").dt if ev.get("DTEND") else None
        all_day = isinstance(dtstart, date) and not isinstance(dtstart, datetime)
        if all_day:
            dtstart = datetime.combine(dtstart, datetime.min.time(), start.tzinfo)
            dtend = datetime.combine(dtend, datetime.min.time(), start.tzinfo) if dtend else dtstart + timedelta(days=1)
        if dtstart.tzinfo is None:
            dtstart = dtstart.replace(tzinfo=start.tzinfo)
        if dtend is not None and getattr(dtend, "tzinfo", 1) is None:
            dtend = dtend.replace(tzinfo=start.tzinfo)
        attendees = ev.get("ATTENDEE") or []
        if not isinstance(attendees, list):
            attendees = [attendees]
        names = []
        for a in attendees:
            cn = a.params.get("CN") if hasattr(a, "params") else None
            names.append(str(cn or str(a).replace("mailto:", "")))
        status = str(ev.get("STATUS") or "").upper()
        if status == "CANCELLED":
            continue
        out.append({
            "uid": f"{ev.get('UID')}|{dtstart.isoformat()}", "title": str(ev.get("SUMMARY") or "(no title)"),
            "start": dtstart.astimezone(timezone.utc).isoformat(),
            "end": (dtend or dtstart + timedelta(hours=1)).astimezone(timezone.utc).isoformat(),
            "all_day": all_day, "location": str(ev.get("LOCATION") or ""),
            "description": str(ev.get("DESCRIPTION") or "")[:1000], "attendees": names[:20],
        })
    return out


def fetch(urls: list[str], tz, days: int = 7, http: httpx.Client | None = None,
          now: datetime | None = None) -> list[dict]:
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    start = datetime.combine(now.date(), datetime.min.time(), tz) - timedelta(days=1)
    end = start + timedelta(days=days + 1)
    client = http or httpx.Client(timeout=15, follow_redirects=True)
    events = []
    for url in urls:
        url = url.strip().replace("webcal://", "https://")
        if not url:
            continue
        try:
            resp = client.get(url)
            resp.raise_for_status()
            events += _events_from_ics(resp.text, start, end)
        except Exception as exc:
            log.warning("Calendar %s could not be read: %s", url[:40], exc)
            raise RuntimeError(f"Couldn't read the calendar ({str(exc)[:120]}). Check the private address.") from exc
    events.sort(key=lambda e: e["start"])
    return events


def cached_events(store, settings, urls: list[str], force: bool = False) -> list[dict]:
    """Events from the cache when fresh, otherwise fetched (errors leave the last good copy in place)."""
    raw = store.get("calendar_cache")
    if raw and not force:
        cache = json.loads(raw)
        if datetime.fromisoformat(cache["at"]) > datetime.now(timezone.utc) - timedelta(minutes=CACHE_MINUTES):
            return cache["events"]
    if not urls:
        return []
    try:
        events = fetch(urls, settings.tz)
    except RuntimeError:
        return json.loads(raw)["events"] if raw else []
    store.put("calendar_cache", json.dumps({"at": datetime.now(timezone.utc).isoformat(), "events": events}))
    return events


def related_items(pa: PAStore, event: dict, limit: int = 6) -> list:
    """Open items that may need discussing in this meeting (title words, attendees, people mentioned)."""
    text = f"{event['title']} {event.get('description', '')}"
    people = {norm(a.split("@")[0]) for a in event.get("attendees", []) if a}
    scored = []
    for row in pa.items(status="active", limit=1000):
        score = similarity(text, f"{row['title']} {row['related_project']}")
        who = norm(row["related_person"] or row["waiting_on"] or row["contact_name"] or "")
        if who and any(who in p or p in who for p in people if p):
            score += 0.5
        if row["related_project"] and norm(row["related_project"]) in norm(text):
            score += 0.4
        if score >= 0.25:
            scored.append((score, row))
    scored.sort(key=lambda x: -x[0])
    return [row for _, row in scored[:limit]]


def meetings_view(pa: PAStore, events: list[dict], tz, now: datetime | None = None) -> dict:
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    today, upcoming, ended = [], [], []
    captured = set(json.loads(pa.store.get(CAPTURED_KEY) or "[]"))
    for e in events:
        start = datetime.fromisoformat(e["start"]).astimezone(tz)
        end = datetime.fromisoformat(e["end"]).astimezone(tz)
        view = {**e, "when": "All day" if e["all_day"] else start.strftime("%H:%M"),
                "day": start.strftime("%a %d %b"), "start_dt": start, "end_dt": end,
                "prep": [{"id": r["id"], "title": r["title"], "kind": r["kind"]} for r in related_items(pa, e)],
                "captured": e["uid"] in captured}
        if start.date() == now.date():
            today.append(view)
            if end <= now and not e["all_day"] and e["uid"] not in captured:
                ended.append(view)
        elif now < start <= now + timedelta(days=7):
            upcoming.append(view)
    return {"today": today, "upcoming": upcoming, "needs_capture": ended}


def capture_actions(pa: PAStore, event: dict, lines: list[str], actor: str, owner_id: str | None = None,
                    due: datetime | None = None) -> list[int]:
    """Turn 'promised actions' from a meeting into follow-up items."""
    ids = []
    for line in lines:
        line = line.strip(" -•\t")
        if not line:
            continue
        ids.append(pa.create_item(actor, kind="follow_up", title=line[:200], source="calendar",
                                  source_ref=event["uid"][:200], related_project=event["title"][:120],
                                  owner_id=owner_id, due_at=due, next_action=f"From meeting: {event['title']}"))
    captured = set(json.loads(pa.store.get(CAPTURED_KEY) or "[]"))
    captured.add(event["uid"])
    pa.store.put(CAPTURED_KEY, json.dumps(sorted(captured)[-500:]))
    return ids
