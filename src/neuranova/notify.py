"""Outbound notifications: WhatsApp Cloud API, or the console while Meta setup is pending.

WhatsApp only allows free-form text within 24 hours of the user's last message to the bot.
Inside that window messages go out as normal text. Outside it they go out through an approved
template with a single body variable ({{1}}); template variables cannot contain newlines, so
line breaks become " | ", and the caller can pass a shorter `teaser` for that case
(e.g. "Draft #4 ready - reply 'drafts' to read it").
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol

import httpx

log = logging.getLogger(__name__)

TEMPLATE_PARAM_LIMIT = 900  # stays under the template body limit with the template's own text
TEXT_LIMIT = 4000           # WhatsApp text messages max out at 4096 characters
SESSION_WINDOW = timedelta(hours=23)  # a little under 24h for safety
LAST_INBOUND_KEY = "whatsapp_last_inbound"


class Notifier(Protocol):
    def send(self, text: str, teaser: str | None = None) -> None: ...


class ConsoleNotifier:
    def send(self, text: str, teaser: str | None = None) -> None:
        print("\n" + "=" * 60 + "\n" + text + "\n" + "=" * 60, flush=True)


def flatten_for_template(text: str) -> str:
    """WhatsApp template params: no newlines/tabs, no more than 4 consecutive spaces."""
    lines = [ln.strip() for ln in text.replace("\t", " ").splitlines() if ln.strip()]
    flat = " | ".join(lines)
    return re.sub(r" {4,}", "   ", flat)


def chunk(text: str, limit: int = TEMPLATE_PARAM_LIMIT, sep: str = " | ") -> list[str]:
    parts: list[str] = []
    while len(text) > limit:
        cut = text.rfind(sep, 0, limit)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut].strip(" |\n"))
        text = text[cut:].strip(" |\n")
    if text:
        parts.append(text)
    return parts


class WhatsAppNotifier:
    def __init__(self, token: str, phone_number_id: str, recipient: str, template: str,
                 language: str = "en", api_version: str = "v22.0", http: httpx.Client | None = None,
                 window_open: Callable[[], bool] = lambda: False):
        if not (token and phone_number_id and recipient):
            raise ValueError("WhatsApp needs WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_RECIPIENT")
        self.url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        self.headers = {"Authorization": f"Bearer {token}"}
        self.recipient = recipient.lstrip("+")
        self.template = template
        self.language = language
        self.http = http or httpx.Client(timeout=30)
        self.window_open = window_open

    def payloads(self, text: str, teaser: str | None = None) -> list[dict]:
        if self.window_open():
            return [
                {"messaging_product": "whatsapp", "to": self.recipient, "type": "text",
                 "text": {"body": part, "preview_url": False}}
                for part in chunk(text, TEXT_LIMIT, sep="\n")
            ]
        return [
            {
                "messaging_product": "whatsapp",
                "to": self.recipient,
                "type": "template",
                "template": {
                    "name": self.template,
                    "language": {"code": self.language},
                    "components": [{"type": "body", "parameters": [{"type": "text", "text": part}]}],
                },
            }
            for part in chunk(flatten_for_template(teaser or text))
        ]

    def send(self, text: str, teaser: str | None = None) -> None:
        for payload in self.payloads(text, teaser):
            resp = self.http.post(self.url, json=payload, headers=self.headers)
            if resp.status_code >= 400:
                raise RuntimeError(f"WhatsApp send failed ({resp.status_code}): {resp.text[:500]}")


def session_open(store) -> Callable[[], bool]:
    """True while we are inside WhatsApp's 24h window after the founder's last message."""
    def check() -> bool:
        last = store.get(LAST_INBOUND_KEY)
        return bool(last) and datetime.now(timezone.utc) - datetime.fromisoformat(last) < SESSION_WINDOW
    return check


def build_notifier(settings, store=None) -> Notifier:
    channel = (settings.secret("NOTIFY_CHANNEL") or "console").lower()
    if channel == "whatsapp":
        return WhatsAppNotifier(
            token=settings.secret("WHATSAPP_ACCESS_TOKEN"),
            phone_number_id=settings.secret("WHATSAPP_PHONE_NUMBER_ID"),
            recipient=settings.secret("WHATSAPP_RECIPIENT"),
            template=settings.secret("WHATSAPP_TEMPLATE_NAME") or "neuranova_update",
            language=settings.secret("WHATSAPP_TEMPLATE_LANG") or "en",
            api_version=settings.secret("WHATSAPP_API_VERSION") or "v22.0",
            window_open=session_open(store) if store is not None else (lambda: False),
        )
    return ConsoleNotifier()
