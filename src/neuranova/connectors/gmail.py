"""Gmail: read the inbox, and send a reply only after you approve it on WhatsApp.

Authorise once on a machine with a browser: `neuranova auth gmail`.
"""

from __future__ import annotations

import base64
import html
import re
from datetime import datetime, timezone
from email.message import EmailMessage as MimeMessage
from email.utils import parseaddr
from pathlib import Path

from ..models import EmailMessage

# readonly to read; send to deliver replies you approved. No modify/delete access.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
INBOX_QUERY = "in:inbox -category:promotions -category:social -category:forums"


def authorize(client_secret_file: str, token_file: str) -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    Path(token_file).parent.mkdir(parents=True, exist_ok=True)
    Path(token_file).write_text(creds.to_json())


def credentials(token_file: str | None = None, token_json: str | None = None, on_refresh=None):
    """Google credentials from the console's saved sign-in (`token_json`) or a token file."""
    import json

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json))
    else:
        creds = Credentials.from_authorized_user_file(token_file)
    if not creds.has_scopes(SCOPES):
        raise RuntimeError("Gmail is missing the send permission - reconnect Gmail")
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            if token_json is not None:
                if on_refresh:
                    on_refresh(creds.to_json())
            else:
                Path(token_file).write_text(creds.to_json())
        else:
            raise RuntimeError("Gmail sign-in has expired - reconnect Gmail")
    return creds


class GmailConnector:
    name = "gmail"

    def __init__(self, token_file: str | None = None, service=None, token_json: str | None = None, on_refresh=None):
        if service is None:
            from googleapiclient.discovery import build

            creds = credentials(token_file, token_json, on_refresh)
            service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        self.api = service.users()

    def send_new(self, to: str, subject: str, body: str) -> str:
        return _send_new(self.api, to, subject, body)

    def profile_email(self) -> str:
        return self.api.getProfile(userId="me").execute().get("emailAddress", "")

    def _list(self, query: str, limit: int = 100) -> list[dict]:
        ids, page = [], None
        while len(ids) < limit:
            resp = self.api.messages().list(userId="me", q=query, pageToken=page, maxResults=50).execute()
            ids.extend(resp.get("messages", []))
            page = resp.get("nextPageToken")
            if not page:
                break
        return ids[:limit]

    def fetch_inbox(self, since: datetime) -> list[EmailMessage]:
        query = f"{INBOX_QUERY} after:{int(since.timestamp())}"
        out = []
        for ref in self._list(query):
            msg = self.api.messages().get(
                userId="me", id=ref["id"], format="metadata", metadataHeaders=["From", "Subject"]
            ).execute()
            if "SENT" in msg.get("labelIds", []):
                continue
            headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
            out.append(EmailMessage(
                source=self.name,
                external_id=msg["id"],
                thread_id=msg["threadId"],
                sender=headers.get("from", ""),
                subject=headers.get("subject", "(no subject)"),
                snippet=msg.get("snippet", ""),
                received_at=datetime.fromtimestamp(int(msg["internalDate"]) / 1000, timezone.utc),
                link=f"https://mail.google.com/mail/u/0/#all/{msg['threadId']}",
            ))
        return out

    def fetch_body(self, external_id: str) -> str:
        msg = self.api.messages().get(userId="me", id=external_id, format="full").execute()
        return extract_text(msg["payload"]) or msg.get("snippet", "")

    def send_reply(self, external_id: str, body: str) -> str:
        orig = self.api.messages().get(
            userId="me", id=external_id, format="metadata",
            metadataHeaders=["From", "Reply-To", "Subject", "Message-ID", "References"],
        ).execute()
        headers = {h["name"].lower(): h["value"] for h in orig["payload"].get("headers", [])}
        subject = headers.get("subject", "")
        mime = MimeMessage()
        mime["To"] = headers.get("reply-to") or headers.get("from", "")
        mime["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        if message_id := headers.get("message-id"):
            mime["In-Reply-To"] = message_id
            mime["References"] = f"{headers.get('references', '')} {message_id}".strip()
        mime.set_content(body)
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        sent = self.api.messages().send(userId="me", body={"raw": raw, "threadId": orig["threadId"]}).execute()
        return sent["id"]

    def latest_replies(self, since: datetime) -> dict[str, datetime]:
        replies: dict[str, datetime] = {}
        for ref in self._list(f"in:sent after:{int(since.timestamp())}", limit=200):
            msg = self.api.messages().get(userId="me", id=ref["id"], format="minimal").execute()
            at = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, timezone.utc)
            if at > replies.get(msg["threadId"], datetime.min.replace(tzinfo=timezone.utc)):
                replies[msg["threadId"]] = at
        return replies


def sender_name(sender: str) -> str:
    name, addr = parseaddr(sender)
    return name or addr or sender


def _send_new(api, to: str, subject: str, body: str) -> str:
    mime = MimeMessage()
    mime["To"], mime["Subject"] = to, subject
    mime.set_content(body)
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    return api.messages().send(userId="me", body={"raw": raw}).execute()["id"]


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def extract_text(payload: dict) -> str:
    """Best plain-text rendering of a Gmail message payload."""
    plain, rich = [], []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            rich.append(_decode(data))
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    if plain:
        return "\n".join(plain).strip()
    if rich:
        text = re.sub(r"(?is)<(script|style).*?</\1>", "", "\n".join(rich))
        text = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", text)
        text = html.unescape(re.sub(r"<[^>]+>", "", text))
        return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()
    return ""
