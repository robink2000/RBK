"""Gmail, read-only. Authorise once on a machine with a browser: `neuranova auth gmail`."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path

from ..models import EmailMessage

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
INBOX_QUERY = "in:inbox -category:promotions -category:social -category:forums"


def authorize(client_secret_file: str, token_file: str) -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    Path(token_file).parent.mkdir(parents=True, exist_ok=True)
    Path(token_file).write_text(creds.to_json())


def _credentials(token_file: str):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            Path(token_file).write_text(creds.to_json())
        else:
            raise RuntimeError("Gmail token is invalid - run `neuranova auth gmail` again")
    return creds


class GmailConnector:
    name = "gmail"

    def __init__(self, token_file: str, service=None):
        if service is None:
            from googleapiclient.discovery import build

            service = build("gmail", "v1", credentials=_credentials(token_file), cache_discovery=False)
        self.api = service.users()

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
            ))
        return out

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
