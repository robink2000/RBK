"""Web server: the WhatsApp webhook (below) and the dashboard (dashboard.py).

WhatsApp webhook: receives the founder's replies (send / edit / skip ...) from Meta.

Security:
- Every POST must carry a valid X-Hub-Signature-256 made with the Meta app secret.
- Only messages from known numbers are acted on: the founder (WHATSAPP_RECIPIENT) and active team
  members with a WhatsApp number on their profile. Members get team-only commands and tools.
- Meta retries deliveries, so each message id is processed once.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timezone
from typing import Callable

from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from .assistant import Assistant
from .commands import handle
from .config import Settings
from .dashboard import mount_dashboard
from .db import Store
from .notify import inbound_key

log = logging.getLogger(__name__)


def _digits(number: str) -> str:
    return re.sub(r"\D", "", number or "")


def valid_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def message_text(msg: dict) -> str | None:
    kind = msg.get("type")
    if kind == "text":
        return msg.get("text", {}).get("body")
    if kind == "button":
        return msg.get("button", {}).get("payload") or msg.get("button", {}).get("text")
    if kind == "interactive":
        inter = msg.get("interactive", {})
        reply = inter.get("button_reply") or inter.get("list_reply") or {}
        return reply.get("id") or reply.get("title")
    return None


def create_app(settings: Settings, agent_factory: Callable, store: Store | None = None) -> FastAPI:
    app = FastAPI(title="NeuraNova agent", docs_url=None, redoc_url=None, openapi_url=None)
    verify_token = settings.secret("WHATSAPP_VERIFY_TOKEN")
    app_secret = settings.secret("WHATSAPP_APP_SECRET")
    owner = _digits(settings.secret("WHATSAPP_RECIPIENT"))
    store = store or Store(settings.db_path, settings.workspace_id, settings.owner_id)
    mount_dashboard(app, settings, agent_factory, store)

    def process(text: str, user_id: str | None) -> None:
        agent = agent_factory()
        user = agent.store.user(user_id) if user_id else None
        try:
            reply = handle(agent, text, chat=lambda t: Assistant(agent, user=user).reply(t), user=user)
        except Exception:
            log.exception("Command failed: %r", text[:80])
            reply = "Sorry, something went wrong handling that. Check the server log."
        if user is None or user["id"] == settings.owner_id:
            agent.notifier.send(reply)
        else:
            agent.notify_user(user, reply)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/webhook")
    def verify(request: Request) -> Response:
        q = request.query_params
        if verify_token and q.get("hub.mode") == "subscribe" and hmac.compare_digest(
                q.get("hub.verify_token", ""), verify_token):
            return PlainTextResponse(q.get("hub.challenge", ""))
        return Response(status_code=403)

    @app.post("/webhook")
    async def receive(request: Request, background: BackgroundTasks) -> Response:
        body = await request.body()
        if not valid_signature(app_secret, body, request.headers.get("x-hub-signature-256")):
            log.warning("Rejected webhook call with a bad or missing signature")
            return Response(status_code=403)
        payload = json.loads(body or b"{}")
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for status in value.get("statuses", []):
                    if status.get("status") == "failed":
                        log.warning("WhatsApp delivery failed: %s", status.get("errors"))
                for msg in value.get("messages", []):
                    sender = _digits(msg.get("from"))
                    if sender == owner:
                        user_id = settings.owner_id
                    elif (member := store.user_by_whatsapp(sender)) is not None:
                        user_id = member["id"]
                    else:
                        log.warning("Ignored WhatsApp message from unknown number %s", msg.get("from"))
                        continue
                    if not store.first_time_seen(msg.get("id", "")):
                        continue
                    store.put(inbound_key(msg.get("from", "")), datetime.now(timezone.utc).isoformat())
                    text = message_text(msg)
                    store.log("whatsapp_in", user=user_id, type=msg.get("type"), text=(text or "")[:200])
                    background.add_task(process, text or "help", user_id)
        return Response(status_code=200)

    return app
