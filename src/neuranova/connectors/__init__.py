"""Mail and task connectors. Mail connectors share one small interface:

    name: str
    fetch_inbox(since) -> list[EmailMessage]
    latest_replies(since) -> dict[thread_id, datetime]   # when *you* last wrote in each thread
    fetch_body(external_id) -> str                        # full plain text, for drafting
    send_reply(external_id, body) -> str                  # only ever called after your approval
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..models import EmailMessage


class MailConnector(Protocol):
    name: str

    def fetch_inbox(self, since: datetime) -> list[EmailMessage]: ...

    def latest_replies(self, since: datetime) -> dict[str, datetime]: ...

    def fetch_body(self, external_id: str) -> str: ...

    def send_reply(self, external_id: str, body: str) -> str: ...
