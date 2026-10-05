"""Web dashboard: goal progress, weekly trends, drafts to approve, tasks and the event log.

Served by the same FastAPI app as the WhatsApp webhook. Login is a password (DASHBOARD_PASSWORD)
plus a signed, HttpOnly, SameSite=Strict session cookie; every form also carries a CSRF token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from jinja2 import DictLoader, Environment, select_autoescape

from .charts import bar_chart
from .config import Settings
from .connectors.gmail import sender_name
from .connectors.todoist import localize
from .db import row_dt
from .progress import EVENT_KINDS, compute, weekly_series

log = logging.getLogger(__name__)

COOKIE = "nn_session"
SESSION_SECONDS = 14 * 24 * 3600
MAX_FAILURES, FAILURE_WINDOW = 5, 15 * 60

STATUS = {
    "good": ("✓", "On track"),
    "warning": ("!", "Needs attention"),
    "critical": ("✕", "Off track"),
    "none": ("–", "No data yet"),
}


# --- session ------------------------------------------------------------------

class Sessions:
    def __init__(self, secret: str):
        self.key = hashlib.sha256(("neuranova-session:" + secret).encode()).digest()

    def _sig(self, data: str) -> str:
        return hmac.new(self.key, data.encode(), hashlib.sha256).hexdigest()

    def issue(self, user: str) -> str:
        data = base64.urlsafe_b64encode(json.dumps({"u": user, "exp": int(time.time()) + SESSION_SECONDS}).encode()).decode()
        return f"{data}.{self._sig(data)}"

    def user(self, cookie: str | None) -> str | None:
        if not cookie or "." not in cookie:
            return None
        data, sig = cookie.rsplit(".", 1)
        if not hmac.compare_digest(sig, self._sig(data)):
            return None
        try:
            payload = json.loads(base64.urlsafe_b64decode(data))
        except ValueError:
            return None
        return payload["u"] if payload.get("exp", 0) > time.time() else None

    def csrf(self, cookie: str) -> str:
        return self._sig("csrf:" + cookie)[:32]


# --- templates -----------------------------------------------------------------

BASE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NeuraNova Agent</title>
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<meta name="theme-color" content="#2a78d6">
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10); --series-1: #2a78d6;
  --good: #0ca30c; --good-ink: #006300; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b;
  --accent: #2a78d6; --accent-ink: #ffffff;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10); --series-1: #3987e5;
    --good-ink: #0ca30c; --accent: #3987e5;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10); --series-1: #3987e5;
  --good-ink: #0ca30c; --accent: #3987e5;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
       font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 1080px; margin: 0 auto; padding: 16px 16px 48px; }
header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
h1 { font-size: 20px; margin: 0; }
h2 { font-size: 16px; margin: 0 0 12px; }
.sub { color: var(--ink-2); font-size: 13px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 16px; min-width: 0; }
.grid3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr)); gap: 16px; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr)); gap: 16px; }
.grid3 .card, .grid2 .card { margin-bottom: 0; }
.row { margin-bottom: 16px; }
.hero { font-size: 32px; font-weight: 650; line-height: 1.1; margin: 8px 0 4px; font-variant-numeric: tabular-nums; }
.kv { display: flex; justify-content: space-between; border-top: 1px solid var(--grid); padding: 6px 0; font-size: 14px; }
.kv span:last-child { font-variant-numeric: tabular-nums; font-weight: 550; }
.pill { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: var(--ink-2); }
.dot { width: 18px; height: 18px; border-radius: 50%; display: inline-grid; place-items: center; color: #fff; font-size: 11px; font-weight: 700; }
.s-good .dot { background: var(--good); } .s-warning .dot { background: var(--warning); color: #0b0b0b; }
.s-critical .dot { background: var(--critical); } .s-none .dot { background: var(--muted); }
.tabs a { color: var(--ink-2); text-decoration: none; padding: 4px 10px; border-radius: 999px; font-size: 13px; border: 1px solid var(--border); }
.tabs a.on { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
svg text { fill: var(--muted); font-size: 11px; }
svg .val { fill: var(--ink-2); font-weight: 600; }
svg .gridline { stroke: var(--grid); stroke-width: 1; }
svg .baseline { stroke: var(--axis); stroke-width: 1; }
svg .bar { fill: var(--series-1); }
svg .hit:hover + .bar, svg .bar:hover { opacity: 0.8; }
svg .hit { fill: transparent; }
details summary { cursor: pointer; color: var(--ink-2); font-size: 13px; margin-top: 4px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
td, th { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--grid); overflow-wrap: anywhere; }
.scroll { overflow-x: auto; }
a { color: var(--accent); }
main, .card { min-width: 0; }
body { overflow-wrap: break-word; }
th { color: var(--ink-2); font-weight: 600; }
ul.list { list-style: none; padding: 0; margin: 0; }
ul.list li { border-top: 1px solid var(--grid); padding: 8px 0; }
ul.list li:first-child { border-top: 0; }
.meta { color: var(--ink-2); font-size: 13px; }
.over { color: var(--critical); font-weight: 600; }
.draft textarea { width: 100%; min-height: 120px; resize: vertical; font: inherit; color: var(--ink); background: var(--page);
                  border: 1px solid var(--border); border-radius: 8px; padding: 8px; }
.needs { background: color-mix(in srgb, var(--warning) 18%, transparent); border-radius: 8px; padding: 6px 10px; margin: 8px 0; font-size: 13px; }
button, .btn { font: inherit; font-size: 14px; border-radius: 8px; padding: 6px 12px; cursor: pointer;
               border: 1px solid var(--border); background: var(--surface); color: var(--ink); }
button.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
button.link { border: 0; background: none; color: var(--muted); padding: 0 4px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
form.inline { display: inline; }
.event-form input, .event-form select { width: 100%; }
input, select { font: inherit; color: var(--ink); background: var(--page); border: 1px solid var(--border); border-radius: 8px; padding: 6px 8px; max-width: 100%; }
.event-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(140px, 100%), 1fr)); gap: 8px; align-items: end; }
.flash { background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--accent); border-radius: 8px; padding: 10px 12px; margin-bottom: 16px; }
.login { max-width: 360px; margin: 12vh auto; }
.login input { width: 100%; margin: 8px 0 12px; }
.empty { color: var(--muted); font-size: 14px; }
</style>
</head>
<body><main>{% block body %}{% endblock %}</main></body>
</html>"""

LOGIN = """{% extends "base" %}{% block body %}
<div class="card login">
  <h1>NeuraNova Agent</h1>
  <p class="sub">Sign in to your dashboard.</p>
  {% if error %}<p class="over">{{ error }}</p>{% endif %}
  <form method="post" action="/login">
    <label for="pw">Password</label>
    <input id="pw" name="password" type="password" autocomplete="current-password" required autofocus>
    <button class="primary" type="submit">Sign in</button>
  </form>
</div>
{% endblock %}"""

CHART = """{% macro chart(c, title, table_label, note="") %}
<svg viewBox="0 0 {{ c.w }} {{ c.h }}" width="100%" role="img" aria-label="{{ title }}">
  {% for g in c.grid %}
  <line class="{{ 'baseline' if loop.first else 'gridline' }}" x1="{{ c.left }}" x2="{{ c.right }}" y1="{{ g.y }}" y2="{{ g.y }}"/>
  <text x="{{ c.left - 6 }}" y="{{ g.y + 4 }}" text-anchor="end">{{ g.label }}</text>
  {% endfor %}
  {% for b in c.bars %}
  <g>
    <rect class="hit" x="{{ b.x - 6 }}" y="0" width="{{ b.w + 12 }}" height="{{ c.base_y }}"><title>{{ b.tip }}</title></rect>
    {% if b.path %}<path class="bar" d="{{ b.path }}"><title>{{ b.tip }}</title></path>
    {% elif b.value is none %}<text x="{{ b.x + b.w / 2 }}" y="{{ c.base_y - 5 }}" text-anchor="middle">–</text>{% endif %}
    <text x="{{ b.x + b.w / 2 }}" y="{{ c.h - 8 }}" text-anchor="middle">{{ b.label }}</text>
  </g>
  {% endfor %}
  {% if c.last %}<text class="val" x="{{ c.last.x + c.last.w / 2 }}" y="{{ c.last.y - 6 }}" text-anchor="middle">{{ '%g' % c.last.value }}{{ '%' if c.percent else '' }}</text>{% endif %}
</svg>
<details><summary>Show as table{% if note %} <span class="sub">({{ note }})</span>{% endif %}</summary>
<table><tr><th>Week of</th><th>{{ table_label }}</th></tr>
{% for b in c.bars %}<tr><td>{{ b.label }}</td><td>{{ '–' if b.value is none else ('%g' % b.value) ~ ('%' if c.percent else '') }}</td></tr>{% endfor %}
</table></details>
{% endmacro %}"""

DASHBOARD = """{% extends "base" %}{% from "chart" import chart %}{% block body %}
<header>
  <div><h1>NeuraNova</h1><div class="sub">{{ today }} · goals, replies and tasks</div></div>
  <div class="tabs">
    {% for d in [7, 30, 90] %}<a href="/?days={{ d }}" class="{{ 'on' if d == days else '' }}">{{ d }} days</a> {% endfor %}
    <form class="inline" method="post" action="/logout"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="link" type="submit">Sign out</button></form>
  </div>
</header>
{% if msg %}<div class="flash" role="status">{{ msg }}</div>{% endif %}

<div class="grid3 row">
  {% set b = p.business %}
  <section class="card">
    <h2>Develop the business</h2>
    <span class="pill s-{{ b.status }}"><span class="dot" aria-hidden="true">{{ labels_for[b.status][0] }}</span>{{ labels_for[b.status][1] }}</span>
    <div class="hero">{{ b.new_leads }}</div><div class="sub">new leads in {{ days }} days</div>
    <div class="kv"><span>Meetings</span><span>{{ b.meetings }}</span></div>
    <div class="kv"><span>Proposals sent</span><span>{{ b.proposals_sent }}</span></div>
    <div class="kv"><span>Deals won / lost</span><span>{{ b.deals_won }} / {{ b.deals_lost }}</span></div>
    <div class="kv"><span>Won value</span><span>{{ '{:,.0f}'.format(b.won_value) }}</span></div>
  </section>
  {% set r = p.responses %}
  <section class="card">
    <h2>Give proper responses</h2>
    <span class="pill s-{{ r.status }}"><span class="dot" aria-hidden="true">{{ labels_for[r.status][0] }}</span>{{ labels_for[r.status][1] }}</span>
    <div class="hero">{{ '–' if r.on_time_pct is none else r.on_time_pct ~ '%' }}</div><div class="sub">replied within {{ sla_hours }} business hours</div>
    <div class="kv"><span>On time / late</span><span>{{ r.on_time }} / {{ r.late }}</span></div>
    <div class="kv"><span>Overdue right now</span><span class="{{ 'over' if r.overdue_now else '' }}">{{ r.overdue_now }}</span></div>
    <div class="kv"><span>Waiting (not yet due)</span><span>{{ r.open }}</span></div>
    <div class="kv"><span>Median time to reply</span><span>{{ '–' if r.median_reply_hours is none else r.median_reply_hours ~ ' h' }}</span></div>
  </section>
  {% set q = p.quality %}
  <section class="card">
    <h2>Deliver high quality</h2>
    <span class="pill s-{{ q.status }}"><span class="dot" aria-hidden="true">{{ labels_for[q.status][0] }}</span>{{ labels_for[q.status][1] }}</span>
    <div class="hero">{{ '–' if q.on_time_pct is none else q.on_time_pct ~ '%' }}</div><div class="sub">deliveries on time</div>
    <div class="kv"><span>Delivered on time / late</span><span>{{ q.deliveries_on_time }} / {{ q.deliveries_late }}</span></div>
    <div class="kv"><span>Rework requests</span><span>{{ q.rework }}</span></div>
    <div class="kv"><span>Feedback 👍 / 👎</span><span>{{ q.feedback_positive }} / {{ q.feedback_negative }}</span></div>
  </section>
</div>

<div class="grid2 row">
  <section class="card"><h2>Replies on time, by week</h2>{{ chart(chart_ontime, "Replies on time by week, percent", "Replies on time", "– = no replies were due that week") }}</section>
  <section class="card"><h2>New leads, by week</h2>{{ chart(chart_leads, "New leads by week", "New leads") }}</section>
</div>

<section class="card" id="drafts">
  <h2>Drafts to approve ({{ drafts|length }})</h2>
  {% for d in drafts %}
  <div class="draft" style="margin-bottom:20px">
    <div><strong>#{{ d.id }} → {{ d.to }}</strong> <span class="meta">· {{ d.subject }}{% if d.deadline %} · reply by {{ d.deadline }}{% endif %}</span></div>
    <div class="meta">{{ d.summary }}</div>
    {% for q in d.needs %}{% if loop.first %}<div class="needs"><strong>Needs you:</strong><ul style="margin:4px 0 0 18px;padding:0">{% endif %}<li>{{ q }}</li>{% if loop.last %}</ul></div>{% endif %}{% endfor %}
    <form method="post" action="/drafts/{{ d.id }}/edit">
      <input type="hidden" name="csrf" value="{{ csrf }}">
      <label class="sr" for="body{{ d.id }}" hidden>Reply text</label>
      <textarea id="body{{ d.id }}" name="body" rows="{{ [d.body.count('\n') + 4, 6]|max }}">{{ d.body }}</textarea>
      <div class="actions">
        <button type="submit">Save changes</button>
        <button class="primary" type="submit" formaction="/drafts/{{ d.id }}/send">Save &amp; send</button>
        <button type="submit" formaction="/drafts/{{ d.id }}/skip">Skip</button>
      </div>
    </form>
  </div>
  {% else %}<p class="empty">No drafts waiting. 🎉</p>{% endfor %}
</section>

<div class="grid2 row">
  <section class="card">
    <h2>Waiting for your reply ({{ waiting|length }})</h2>
    <ul class="list">
    {% for w in waiting %}
      <li><strong>{{ w.from }}</strong> · {{ w.subject }}<div class="meta">{{ w.summary }}</div>
        <div class="meta {{ 'over' if w.overdue else '' }}">{{ 'Overdue since' if w.overdue else 'Reply by' }} {{ w.deadline }}{% if w.link %} · <a href="{{ w.link }}" target="_blank" rel="noopener">open email</a>{% endif %}</div></li>
    {% else %}<li class="empty">Nothing waiting. 🎉</li>{% endfor %}
    </ul>
  </section>
  <section class="card">
    <h2>Tasks today &amp; overdue ({{ tasks|length }})</h2>
    {% if tasks_error %}<p class="empty">{{ tasks_error }}</p>{% endif %}
    <ul class="list">
    {% for t in tasks %}
      <li><strong>{{ t.label }}</strong> {{ t.content }}<div class="meta {{ 'over' if t.overdue else '' }}">{{ t.when }} · <a href="{{ t.url }}" target="_blank" rel="noopener">open</a></div></li>
    {% else %}{% if not tasks_error %}<li class="empty">No tasks due.</li>{% endif %}{% endfor %}
    </ul>
  </section>
</div>

<section class="card" id="events">
  <h2>Log progress</h2>
  <p class="sub">Record what happened so the goal cards stay accurate. You can also just tell the bot on WhatsApp, e.g. "delivered the Acme site on time".</p>
  <form class="event-form" method="post" action="/events">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <label>What<br><select name="kind">{% for k, v in kinds.items() %}<option value="{{ k }}">{{ v }}</option>{% endfor %}</select></label>
    <label>Client<br><input name="client" maxlength="120"></label>
    <label>Value<br><input name="value" inputmode="decimal" maxlength="20"></label>
    <label>Date<br><input name="on_date" type="date" value="{{ today_iso }}"></label>
    <label>Note<br><input name="note" maxlength="300"></label>
    <button class="primary" type="submit">Add</button>
  </form>
  <div class="scroll"><table style="margin-top:12px">
    <tr><th>Date</th><th>What</th><th>Client</th><th>Value</th><th>Note</th><th></th></tr>
    {% for e in events %}
    <tr><td>{{ e.on_date }}</td><td>{{ kinds.get(e.kind, e.kind) }}</td><td>{{ e.client }}</td><td>{{ '' if e.value is none else '{:,.0f}'.format(e.value) }}</td><td>{{ e.note }}</td>
      <td><form class="inline" method="post" action="/events/{{ e.id }}/delete"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="link" type="submit" aria-label="Delete event">✕</button></form></td></tr>
    {% else %}<tr><td colspan="6" class="empty">Nothing logged yet.</td></tr>{% endfor %}
  </table></div>
</section>

<section class="card">
  <h2>Agent activity</h2>
  <div class="scroll"><table>{% for a in activity %}<tr><td class="meta" style="white-space:nowrap">{{ a.at }}</td><td>{{ a.action }}</td><td class="meta">{{ a.detail }}</td></tr>{% endfor %}</table></div>
</section>
{% endblock %}"""

MANIFEST = {
    "name": "NeuraNova Agent", "short_name": "NeuraNova", "start_url": "/", "display": "standalone",
    "background_color": "#f9f9f7", "theme_color": "#2a78d6",
    "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}],
}

ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#2a78d6"/>
<path d="M18 46V18l28 28V18" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/></svg>"""

env = Environment(loader=DictLoader({"base": BASE, "login": LOGIN, "dashboard": DASHBOARD, "chart": CHART}),
                  autoescape=select_autoescape(default=True, default_for_string=True))


# --- routes ------------------------------------------------------------------

def mount_dashboard(app: FastAPI, settings: Settings, agent_factory: Callable) -> None:
    password = settings.secret("DASHBOARD_PASSWORD")
    secret = settings.secret("DASHBOARD_SECRET")
    secure_cookie = settings.secret("DASHBOARD_INSECURE_COOKIE") != "1"
    sessions = Sessions(secret) if secret else None
    failures: dict[str, list[float]] = {}

    def enabled() -> bool:
        return bool(password and sessions)

    def current(request: Request) -> tuple[str | None, str]:
        cookie = request.cookies.get(COOKIE, "")
        return (sessions.user(cookie) if sessions else None), cookie

    def check_csrf(request: Request, token: str) -> bool:
        user, cookie = current(request)
        return bool(user) and hmac.compare_digest(token or "", sessions.csrf(cookie))

    def back(msg: str = "", anchor: str = "") -> RedirectResponse:
        return RedirectResponse(f"/?msg={quote(msg)}{anchor}" if msg else f"/{anchor}", status_code=303)

    def page(name: str, status: int = 200, **ctx) -> HTMLResponse:
        return HTMLResponse(env.get_template(name).render(**ctx), status_code=status,
                            headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY",
                                     "Referrer-Policy": "same-origin"})

    @app.get("/manifest.webmanifest")
    def manifest() -> Response:
        return Response(json.dumps(MANIFEST), media_type="application/manifest+json")

    @app.get("/icon.svg")
    def icon() -> Response:
        return Response(ICON, media_type="image/svg+xml")

    @app.get("/login")
    def login_form() -> HTMLResponse:
        if not enabled():
            return page("login", 503, error="Dashboard is off: set DASHBOARD_PASSWORD and DASHBOARD_SECRET in .env.")
        return page("login")

    @app.post("/login")
    def login(request: Request, password_in: str = Form("", alias="password")) -> Response:
        if not enabled():
            return page("login", 503, error="Dashboard is off.")
        ip = request.client.host if request.client else "?"
        now = time.time()
        recent = [t for t in failures.get(ip, []) if now - t < FAILURE_WINDOW]
        if len(recent) >= MAX_FAILURES:
            return page("login", 429, error="Too many attempts. Try again in 15 minutes.")
        if not hmac.compare_digest(password_in.encode(), password.encode()):
            failures[ip] = recent + [now]
            log.warning("Failed dashboard login from %s", ip)
            time.sleep(1)
            return page("login", 401, error="Wrong password.")
        failures.pop(ip, None)
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(COOKIE, sessions.issue(settings.owner_id), max_age=SESSION_SECONDS, httponly=True,
                        secure=secure_cookie, samesite="strict")
        return resp

    @app.post("/logout")
    def logout(request: Request, csrf: str = Form("")) -> Response:
        resp = RedirectResponse("/login", status_code=303)
        if check_csrf(request, csrf):
            resp.delete_cookie(COOKIE)
        return resp

    @app.get("/")
    def dashboard(request: Request, days: int = 7, msg: str = "") -> Response:
        user, cookie = current(request)
        if not user:
            return RedirectResponse("/login", status_code=303)
        days = days if days in (7, 30, 90) else 7
        agent = agent_factory()
        store, tz = agent.store, settings.tz
        now = datetime.now(timezone.utc)

        series = weekly_series(store, tz, weeks=8)
        labels = [w["label"] for w in series]

        drafts = []
        for d in store.pending_drafts():
            drafts.append({"id": d["id"], "to": sender_name(d["sender"]), "subject": d["subject"],
                           "summary": d["summary"], "body": d["body"], "needs": json.loads(d["needs_input"] or "[]"),
                           "deadline": agent._fmt_deadline(d) if d["reply_deadline"] else ""})
        waiting = [{"from": sender_name(r["sender"]), "subject": r["subject"], "summary": r["summary"],
                    "deadline": agent._fmt_deadline(r), "link": r["link"],
                    "overdue": bool(r["reply_deadline"] and row_dt(r["reply_deadline"]) < now)}
                   for r in store.awaiting_reply()[:20]]

        tasks, tasks_error = [], ""
        if agent.todoist:
            try:
                today = now.astimezone(tz).date().isoformat()
                for t in sorted(agent.todoist.today_and_overdue(), key=lambda t: (-t.priority, t.due_date or "")):
                    when = localize(t, tz)
                    tasks.append({"label": t.label, "content": t.content, "url": t.url,
                                  "overdue": bool(t.due_date and t.due_date < today),
                                  "when": when.strftime("%a %H:%M") if when else (t.due_date or "")})
            except Exception:
                log.exception("Dashboard could not load Todoist")
                tasks_error = "Couldn't reach Todoist right now."
        else:
            tasks_error = "Todoist is not connected."

        activity = [{"at": row_dt(a["at"]).astimezone(tz).strftime("%d %b %H:%M"), "action": a["action"],
                     "detail": a["detail"][:160]} for a in store.recent_activity(15)]
        return page(
            "dashboard", days=days, msg=msg, csrf=sessions.csrf(cookie), labels_for=STATUS,
            today=now.astimezone(tz).strftime("%A %d %B %Y"), today_iso=now.astimezone(tz).date().isoformat(),
            p=compute(store, tz, days=days), sla_hours=f"{settings.sla_hours:g}",
            chart_ontime=bar_chart(labels, [w["on_time_pct"] for w in series], percent=True),
            chart_leads=bar_chart(labels, [w["new_leads"] for w in series]),
            drafts=drafts, waiting=waiting, tasks=tasks, tasks_error=tasks_error,
            kinds=EVENT_KINDS, events=store.recent_events(15), activity=activity,
        )

    def draft_action(request: Request, csrf: str, action: Callable[[], str]) -> Response:
        if not check_csrf(request, csrf):
            return Response("Session expired - reload the page and sign in again.", status_code=403)
        return back(action(), "#drafts")

    @app.post("/drafts/{draft_id}/edit")
    def edit(request: Request, draft_id: int, csrf: str = Form(""), body: str = Form("")) -> Response:
        def run():
            agent = agent_factory()
            agent.edit_draft(draft_id, body)
            return f"Saved draft #{draft_id}."
        return draft_action(request, csrf, run)

    @app.post("/drafts/{draft_id}/send")
    def send(request: Request, draft_id: int, csrf: str = Form(""), body: str = Form("")) -> Response:
        def run():
            agent = agent_factory()
            d = agent.store.draft(draft_id)
            if d and body.strip() and body.strip() != d["body"]:
                agent.edit_draft(draft_id, body)
            return agent.send_draft(draft_id)
        return draft_action(request, csrf, run)

    @app.post("/drafts/{draft_id}/skip")
    def skip(request: Request, draft_id: int, csrf: str = Form("")) -> Response:
        return draft_action(request, csrf, lambda: agent_factory().skip_draft(draft_id))

    @app.post("/events")
    def add_event(request: Request, csrf: str = Form(""), kind: str = Form(...), client: str = Form(""),
                  value: str = Form(""), on_date: str = Form(""), note: str = Form("")) -> Response:
        if not check_csrf(request, csrf):
            return Response("Session expired - reload the page and sign in again.", status_code=403)
        if kind not in EVENT_KINDS:
            return back("Unknown event type.", "#events")
        try:
            amount = float(value.replace(",", "")) if value.strip() else None
            day = datetime.strptime(on_date, "%Y-%m-%d").date().isoformat() if on_date else \
                datetime.now(settings.tz).date().isoformat()
        except ValueError:
            return back("Value must be a number and date YYYY-MM-DD.", "#events")
        agent_factory().store.add_event(day, kind, client.strip()[:120], amount, note.strip()[:300], source="dashboard")
        return back(f"Logged: {EVENT_KINDS[kind]}.", "#events")

    @app.post("/events/{event_id}/delete")
    def delete_event(request: Request, event_id: int, csrf: str = Form("")) -> Response:
        if not check_csrf(request, csrf):
            return Response("Session expired - reload the page and sign in again.", status_code=403)
        agent_factory().store.delete_event(event_id)
        return back("Event deleted.", "#events")
