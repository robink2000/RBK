"""Web dashboard: goal progress, weekly trends, team board, drafts to approve, tasks and the event log.

Served by the same FastAPI app as the WhatsApp webhook. Each person signs in with their email and
password (the founder's password is DASHBOARD_PASSWORD; teammates set theirs from an invite link).
Sessions are signed, HttpOnly, SameSite=Strict cookies; every form also carries a CSRF token.
Members never see the founder's mailbox, drafts, personal Todoist or the agent activity log.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from .charts import bar_chart
from .config import Settings
from .connectors.gmail import sender_name
from .connectors.todoist import localize
from .db import row_dt
from .progress import EVENT_KINDS, compute, team_stats, weekly_series
from .team import (TeamError, accept_invite, authenticate, can_change, create_invite, create_reset_link,
                   ensure_owner, parse_due, set_active, token_hash)
from .templates import env, manifest as build_manifest

log = logging.getLogger(__name__)

COOKIE = "nn_session"
BUILTIN_LOGO = Path(__file__).parent / "static" / "neuranova-logo.png"
LOGO_TYPES = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".webp": "image/webp"}
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


# --- routes ------------------------------------------------------------------

def mount_dashboard(app: FastAPI, settings: Settings, agent_factory: Callable, store=None) -> None:
    secret = settings.secret("DASHBOARD_SECRET")
    secure_cookie = settings.secret("DASHBOARD_INSECURE_COOKIE") != "1"
    public_url = settings.secret("PUBLIC_URL").rstrip("/")
    sessions = Sessions(secret) if secret else None
    brand = dict(settings.brand or {}) or dict(env.globals["brand"])
    logo_path, logo_type = BUILTIN_LOGO, "image/png"
    if brand.get("logo"):
        custom = Path(brand["logo"])
        if custom.is_file() and custom.suffix.lower() in LOGO_TYPES:
            logo_path, logo_type = custom, LOGO_TYPES[custom.suffix.lower()]
        else:
            log.warning("Brand logo %s not found or not .svg/.png/.jpg/.webp; using the NeuraNova logo", custom)
    env.globals["brand"] = brand
    failures: dict[str, list[float]] = {}
    if store is not None and settings.secret("DASHBOARD_PASSWORD"):
        ensure_owner(store, settings)

    def enabled() -> bool:
        return bool(settings.secret("DASHBOARD_PASSWORD") and sessions)

    def current(request: Request, agent) -> tuple:
        cookie = request.cookies.get(COOKIE, "")
        user_id = sessions.user(cookie) if sessions else None
        user = agent.store.user(user_id) if user_id else None
        return (user if user and user["active"] else None), cookie

    def page(_template: str, code: int = 200, **ctx) -> HTMLResponse:
        return HTMLResponse(env.get_template(_template).render(**ctx), status_code=code,
                            headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY",
                                     "Referrer-Policy": "no-referrer"})

    def back(path: str = "/", msg: str = "") -> RedirectResponse:
        # Same-site paths only: "//evil" and "/\\evil" are treated as other sites by browsers.
        path = path if path.startswith("/") and path[1:2] not in ("/", "\\") else "/"
        base, _, anchor = path.partition("#")
        sep = "&" if "?" in base else "?"
        url = f"{base}{sep}msg={quote(msg)}" if msg else base
        return RedirectResponse(url + (f"#{anchor}" if anchor else ""), status_code=303)

    def guarded(request: Request, csrf: str, admin: bool = False):
        """(agent, user) for a valid signed-in POST, else an error Response."""
        agent = agent_factory()
        user, cookie = current(request, agent)
        if not user or not hmac.compare_digest(csrf or "", sessions.csrf(cookie)):
            return Response("Session expired - reload the page and sign in again.", status_code=403)
        if admin and user["role"] != "admin":
            return Response("Admins only.", status_code=403)
        return agent, user

    def today_text() -> str:
        return datetime.now(settings.tz).strftime("%A %d %B %Y")

    def task_view(t, me, now) -> dict:
        due = row_dt(t["due_at"])
        return {**dict(t), "due": due.astimezone(settings.tz).strftime("%a %d %b %H:%M") if due else "",
                "overdue": bool(due and due < now and t["status"] != "done"),
                "can_change": can_change(me, t)}

    @app.get("/manifest.webmanifest")
    def manifest() -> Response:
        data = build_manifest(brand)
        if logo_path != BUILTIN_LOGO:
            data["icons"] = [{"src": "/brand/logo", "sizes": "any", "type": logo_type}]
        return Response(json.dumps(data), media_type="application/manifest+json")

    @app.get("/brand/logo")
    def brand_logo() -> Response:
        return Response(logo_path.read_bytes(), media_type=logo_type,
                        headers={"Cache-Control": "public, max-age=3600",
                                 "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})

    # --- sign in / out / join -------------------------------------------------

    @app.get("/login")
    def login_form() -> HTMLResponse:
        if not enabled():
            return page("login", 503, error="Dashboard is off: set DASHBOARD_PASSWORD and DASHBOARD_SECRET in .env.")
        return page("login")

    @app.post("/login")
    def login(request: Request, email: str = Form(""), password_in: str = Form("", alias="password")) -> Response:
        if not enabled():
            return page("login", 503, error="Dashboard is off.")
        ip = request.client.host if request.client else "?"
        now = time.time()
        recent = [t for t in failures.get(ip, []) if now - t < FAILURE_WINDOW]
        if len(recent) >= MAX_FAILURES:
            return page("login", 429, error="Too many attempts. Try again in 15 minutes.", email=email)
        user = authenticate(agent_factory().store, email, password_in)
        if user is None:
            failures[ip] = recent + [now]
            log.warning("Failed dashboard login from %s", ip)
            time.sleep(1)
            return page("login", 401, error="Wrong email or password.", email=email)
        failures.pop(ip, None)
        return signed_in(user["id"])

    def signed_in(user_id: str) -> Response:
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(COOKIE, sessions.issue(user_id), max_age=SESSION_SECONDS, httponly=True,
                        secure=secure_cookie, samesite="strict")
        return resp

    @app.post("/logout")
    def logout(request: Request, csrf: str = Form("")) -> Response:
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(COOKIE)
        return resp

    @app.get("/join/{token}")
    def join_form(token: str) -> HTMLResponse:
        if not enabled():
            return page("join", 503, error="Dashboard is off.")
        invite = agent_factory().store.invite(token_hash(token))
        if invite is None:
            return page("join", 404, error="This link has expired or was already used. Ask your admin for a new one.")
        return page("join", invite=invite, token=token)

    @app.post("/join/{token}")
    def join(token: str, password_in: str = Form("", alias="password")) -> Response:
        if not enabled():
            return page("join", 503, error="Dashboard is off.")
        store_ = agent_factory().store
        try:
            user_id = accept_invite(store_, token, password_in)
        except TeamError as exc:
            invite = store_.invite(token_hash(token))
            return page("join", 400, error=str(exc), invite=invite, token=token if invite else "")
        return signed_in(user_id)

    # --- home -------------------------------------------------------------------

    @app.get("/")
    def dashboard(request: Request, days: int = 7, msg: str = "") -> Response:
        agent = agent_factory()
        me, cookie = current(request, agent)
        if not me:
            return RedirectResponse("/login", status_code=303)
        days = days if days in (7, 30, 90) else 7
        store, tz = agent.store, settings.tz
        now = datetime.now(timezone.utc)
        is_owner = me["id"] == settings.owner_id

        series = weekly_series(store, tz, weeks=8)
        labels = [w["label"] for w in series]
        ctx = dict(
            me=me, is_owner=is_owner, days=days, msg=msg, csrf=sessions.csrf(cookie), labels_for=STATUS,
            today=today_text(), today_iso=now.astimezone(tz).date().isoformat(),
            p=compute(store, tz, days=days), sla_hours=f"{settings.sla_hours:g}",
            chart_ontime=bar_chart(labels, [w["on_time_pct"] for w in series], percent=True),
            chart_leads=bar_chart(labels, [w["new_leads"] for w in series]),
            members=store.users(),
            my_tasks=[task_view(t, me, now) for t in store.team_tasks("open", assignee_id=me["id"])],
            kinds=EVENT_KINDS, events=store.recent_events(15),
            drafts=[], waiting=[], tasks=[], tasks_error="", activity=[],
        )
        if is_owner:
            for d in store.pending_drafts():
                ctx["drafts"].append({"id": d["id"], "to": sender_name(d["sender"]), "subject": d["subject"],
                                      "summary": d["summary"], "body": d["body"],
                                      "needs": json.loads(d["needs_input"] or "[]"),
                                      "deadline": agent._fmt_deadline(d) if d["reply_deadline"] else ""})
            ctx["waiting"] = [{"id": r["id"], "from": sender_name(r["sender"]), "subject": r["subject"],
                               "summary": r["summary"], "deadline": agent._fmt_deadline(r), "link": r["link"],
                               "overdue": bool(r["reply_deadline"] and row_dt(r["reply_deadline"]) < now)}
                              for r in store.awaiting_reply()[:20]]
            if agent.todoist:
                try:
                    today = now.astimezone(tz).date().isoformat()
                    for t in sorted(agent.todoist.today_and_overdue(), key=lambda t: (-t.priority, t.due_date or "")):
                        when = localize(t, tz)
                        ctx["tasks"].append({"label": t.label, "content": t.content, "url": t.url,
                                             "overdue": bool(t.due_date and t.due_date < today),
                                             "when": when.strftime("%a %H:%M") if when else (t.due_date or "")})
                except Exception:
                    log.exception("Dashboard could not load Todoist")
                    ctx["tasks_error"] = "Couldn't reach Todoist right now."
            else:
                ctx["tasks_error"] = "Todoist is not connected."
            ctx["activity"] = [{"at": row_dt(a["at"]).astimezone(tz).strftime("%d %b %H:%M"), "action": a["action"],
                                "detail": a["detail"][:160]} for a in store.recent_activity(15)]
        return page("dashboard", **ctx)

    # --- drafts (founder only: they send from the founder's mailbox) ------------------

    def draft_action(request: Request, csrf: str, action: Callable) -> Response:
        g = guarded(request, csrf)
        if isinstance(g, Response):
            return g
        agent, me = g
        if me["id"] != settings.owner_id:
            return Response("Only the founder can act on reply drafts.", status_code=403)
        return back("/#drafts", action(agent))

    @app.post("/drafts/{draft_id}/edit")
    def edit(request: Request, draft_id: int, csrf: str = Form(""), body: str = Form("")) -> Response:
        def run(agent):
            agent.edit_draft(draft_id, body)
            return f"Saved draft #{draft_id}."
        return draft_action(request, csrf, run)

    @app.post("/drafts/{draft_id}/send")
    def send(request: Request, draft_id: int, csrf: str = Form(""), body: str = Form("")) -> Response:
        def run(agent):
            d = agent.store.draft(draft_id)
            if d and body.strip() and body.strip() != d["body"]:
                agent.edit_draft(draft_id, body)
            return agent.send_draft(draft_id)
        return draft_action(request, csrf, run)

    @app.post("/drafts/{draft_id}/skip")
    def skip(request: Request, draft_id: int, csrf: str = Form("")) -> Response:
        return draft_action(request, csrf, lambda agent: agent.skip_draft(draft_id))

    # --- events -----------------------------------------------------------------------

    @app.post("/events")
    def add_event(request: Request, csrf: str = Form(""), kind: str = Form(...), client: str = Form(""),
                  value: str = Form(""), on_date: str = Form(""), note: str = Form("")) -> Response:
        g = guarded(request, csrf)
        if isinstance(g, Response):
            return g
        agent, me = g
        if kind not in EVENT_KINDS:
            return back("/#events", "Unknown event type.")
        try:
            amount = float(value.replace(",", "")) if value.strip() else None
            day = datetime.strptime(on_date, "%Y-%m-%d").date().isoformat() if on_date else \
                datetime.now(settings.tz).date().isoformat()
        except ValueError:
            return back("/#events", "Value must be a number and date YYYY-MM-DD.")
        note = note.strip()[:300]
        if me["id"] != settings.owner_id:
            note = f"{note} (by {me['name']})".strip()
        agent.store.add_event(day, kind, client.strip()[:120], amount, note, source="dashboard")
        return back("/#events", f"Logged: {EVENT_KINDS[kind]}.")

    @app.post("/events/{event_id}/delete")
    def delete_event(request: Request, event_id: int, csrf: str = Form("")) -> Response:
        g = guarded(request, csrf, admin=True)
        if isinstance(g, Response):
            return g
        g[0].store.delete_event(event_id)
        return back("/#events", "Event deleted.")

    # --- team -------------------------------------------------------------------------

    @app.get("/team")
    def team_page(request: Request, view: str = "open", msg: str = "") -> Response:
        agent = agent_factory()
        me, cookie = current(request, agent)
        if not me:
            return RedirectResponse("/login", status_code=303)
        store = agent.store
        now = datetime.now(timezone.utc)
        view = view if view in ("open", "mine", "blocked", "done") else "open"
        if view == "mine":
            rows = store.team_tasks("open", assignee_id=me["id"])
        elif view == "blocked":
            rows = store.team_tasks("blocked")
        elif view == "done":
            rows = list(reversed(store.team_tasks("done", limit=200)))[:50]
        else:
            rows = store.team_tasks("open")
        invites = []
        if me["role"] == "admin":
            invites = [{**dict(i), "expires": row_dt(i["expires_at"]).astimezone(settings.tz).strftime("%d %b")}
                       for i in store.open_invites()]
        return page("team", me=me, csrf=sessions.csrf(cookie), today=today_text(), msg=msg, view=view,
                    tasks=[task_view(t, me, now) for t in rows], members=store.users(),
                    stats=team_stats(store, days=7), people=store.users(active_only=False),
                    invites=invites, owner_id=settings.owner_id)

    def task_action(request: Request, csrf: str, back_to: str, action: Callable) -> Response:
        g = guarded(request, csrf)
        if isinstance(g, Response):
            return g
        agent, me = g
        try:
            return back(back_to or "/team", action(agent, me))
        except TeamError as exc:
            return back(back_to or "/team", str(exc))

    @app.post("/team/tasks")
    def new_task(request: Request, csrf: str = Form(""), title: str = Form(""), assignee: str = Form(""),
                 due_date: str = Form(""), due_time: str = Form(""), notes: str = Form("")) -> Response:
        def run(agent, me):
            person = agent.store.user(assignee)
            if person is None:
                raise TeamError("Pick a teammate.")
            due = parse_due(f"{due_date}T{due_time}" if due_date and due_time else due_date,
                            settings.tz, settings.working_hours.end)
            task_id = agent.assign_team_task(me, person, title[:200], due, notes[:500])
            return f"Added #{task_id} for {person['name']}."
        return task_action(request, csrf, "/team#board", run)

    @app.post("/team/tasks/from-email/{email_id}")
    def delegate_email(request: Request, email_id: int, csrf: str = Form(""), assignee: str = Form(""),
                       due_date: str = Form("")) -> Response:
        def run(agent, me):
            if me["id"] != settings.owner_id:
                raise TeamError("Only the founder can delegate their email.")
            email = agent.store.email(email_id)
            person = agent.store.user(assignee)
            if email is None or person is None:
                raise TeamError("Email or teammate not found.")
            due = parse_due(due_date, settings.tz, settings.working_hours.end) if due_date else \
                row_dt(email["reply_deadline"])
            title = f"Handle email from {sender_name(email['sender'])}: {email['subject']}"[:200]
            notes = f"{email['summary']} Next step: {email['suggested_action']}"
            task_id = agent.assign_team_task(me, person, title, due, notes, email_id=email_id)
            return f"Delegated to {person['name']} as #{task_id}. You still owe the reply unless they answer for you."
        return task_action(request, csrf, "/#mytasks", run)

    @app.post("/team/tasks/{task_id}/done")
    def task_done(request: Request, task_id: int, csrf: str = Form(""), back_to: str = Form("", alias="back")) -> Response:
        return task_action(request, csrf, back_to, lambda agent, me: agent.complete_team_task(me, task_id))

    @app.post("/team/tasks/{task_id}/blocked")
    def task_blocked(request: Request, task_id: int, csrf: str = Form(""), reason: str = Form(""),
                     back_to: str = Form("", alias="back")) -> Response:
        return task_action(request, csrf, back_to, lambda agent, me: agent.block_team_task(me, task_id, reason[:300]))

    @app.post("/team/tasks/{task_id}/reopen")
    def task_reopen(request: Request, task_id: int, csrf: str = Form(""), back_to: str = Form("", alias="back")) -> Response:
        return task_action(request, csrf, back_to, lambda agent, me: agent.reopen_team_task(me, task_id))

    @app.post("/team/tasks/{task_id}/reassign")
    def task_reassign(request: Request, task_id: int, csrf: str = Form(""), assignee: str = Form(""),
                      back_to: str = Form("", alias="back")) -> Response:
        def run(agent, me):
            person = agent.store.user(assignee)
            if person is None or not person["active"]:
                raise TeamError("Pick an active teammate.")
            return agent.reassign_team_task(me, task_id, person)
        return task_action(request, csrf, back_to, run)

    # --- people (admins) ---------------------------------------------------------------

    def link_page(request: Request, cookie_user, csrf_cookie: str, token: str, title: str, person: dict) -> Response:
        base = public_url or str(request.base_url).rstrip("/")
        return page("link", me=cookie_user, csrf=sessions.csrf(csrf_cookie), today=today_text(), title=title,
                    link=f"{base}/join/{token}", name=person["name"], email=person["email"])

    @app.post("/team/invite")
    def invite(request: Request, csrf: str = Form(""), name: str = Form(""), email: str = Form(""),
               role: str = Form("member"), whatsapp: str = Form("")) -> Response:
        g = guarded(request, csrf, admin=True)
        if isinstance(g, Response):
            return g
        agent, me = g
        try:
            token = create_invite(agent.store, me, email, name[:80], role, whatsapp)
        except TeamError as exc:
            return back("/team#people", str(exc))
        return link_page(request, me, request.cookies.get(COOKIE, ""), token, f"Invite link for {name}",
                         {"name": name, "email": email})

    @app.post("/team/people/{user_id}/reset")
    def reset(request: Request, user_id: str, csrf: str = Form("")) -> Response:
        g = guarded(request, csrf, admin=True)
        if isinstance(g, Response):
            return g
        agent, me = g
        if user_id == settings.owner_id:
            return back("/team#people", "The founder's password is set in .env (DASHBOARD_PASSWORD).")
        try:
            token = create_reset_link(agent.store, me, user_id)
        except TeamError as exc:
            return back("/team#people", str(exc))
        person = agent.store.user(user_id)
        return link_page(request, me, request.cookies.get(COOKIE, ""), token,
                         f"Password reset link for {person['name']}", dict(person))

    @app.post("/team/people/{user_id}/update")
    def update_person(request: Request, user_id: str, csrf: str = Form(""), role: str = Form("member"),
                      whatsapp: str = Form("")) -> Response:
        g = guarded(request, csrf, admin=True)
        if isinstance(g, Response):
            return g
        agent, me = g
        if user_id in (me["id"], settings.owner_id) or role not in ("admin", "member") or not agent.store.user(user_id):
            return back("/team#people", "Not allowed.")
        from .team import digits
        agent.store.set_user_fields(user_id, role=role, whatsapp=digits(whatsapp))
        agent.store.log("member_updated", by=me["id"], user=user_id, role=role)
        return back("/team#people", "Saved.")

    @app.post("/team/people/{user_id}/{action}")
    def person_active(request: Request, user_id: str, action: str, csrf: str = Form("")) -> Response:
        g = guarded(request, csrf, admin=True)
        if isinstance(g, Response):
            return g
        agent, me = g
        if action not in ("activate", "deactivate") or user_id == settings.owner_id:
            return back("/team#people", "Not allowed.")
        try:
            set_active(agent.store, me, user_id, action == "activate")
        except TeamError as exc:
            return back("/team#people", str(exc))
        return back("/team#people", "Saved.")

    @app.post("/team/invites/{th}/revoke")
    def revoke(request: Request, th: str, csrf: str = Form("")) -> Response:
        g = guarded(request, csrf, admin=True)
        if isinstance(g, Response):
            return g
        g[0].store.revoke_invite(th)
        return back("/team#people", "Invite revoked.")
