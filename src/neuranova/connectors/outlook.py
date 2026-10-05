"""Outlook / Microsoft 365 via Microsoft Graph: read the inbox, send replies you approved.

Authorise once: `neuranova auth outlook`.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..models import EmailMessage

SCOPES = ["Mail.Read", "Mail.Send"]
GRAPH = "https://graph.microsoft.com/v1.0"


def make_app(client_id: str, tenant: str = "common", cache_text: str = "", client_secret: str = ""):
    """MSAL app with a token cache. A client secret means a "Web" app registration (server sign-in);
    without one it's a public client (device code, or localhost redirect)."""
    import msal

    cache = msal.SerializableTokenCache()
    if cache_text:
        cache.deserialize(cache_text)
    authority = f"https://login.microsoftonline.com/{tenant or 'common'}"
    if client_secret:
        app = msal.ConfidentialClientApplication(client_id, client_credential=client_secret, authority=authority,
                                                 token_cache=cache)
    else:
        app = msal.PublicClientApplication(client_id, authority=authority, token_cache=cache)
    return app, cache


def _app(client_id: str, tenant: str, cache_file: str):
    text = Path(cache_file).read_text() if Path(cache_file).exists() else ""
    return make_app(client_id, tenant, text)


def token_from_cache(client_id: str, tenant: str, cache_text: str, client_secret: str = "", on_change=None):
    """(access_token, account username) from a saved cache; refreshes silently when needed."""
    app, cache = make_app(client_id, tenant, cache_text, client_secret)
    accounts = app.get_accounts()
    result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
    if not result or "access_token" not in result:
        raise RuntimeError("Outlook sign-in has expired - reconnect Outlook")
    if cache.has_state_changed and on_change:
        on_change(cache.serialize())
    return result["access_token"], accounts[0].get("username", "")


def _save(cache, cache_file: str) -> None:
    if cache.has_state_changed:
        Path(cache_file).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_file).write_text(cache.serialize())


def authorize(client_id: str, tenant: str, cache_file: str) -> None:
    """Device-code sign-in: works on a headless server, you approve on your phone or laptop."""
    app, cache = _app(client_id, tenant, cache_file)
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"Could not start Microsoft sign-in: {flow}")
    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"Microsoft sign-in failed: {result.get('error_description')}")
    _save(cache, cache_file)


def access_token(client_id: str, tenant: str, cache_file: str) -> str:
    app, cache = _app(client_id, tenant, cache_file)
    accounts = app.get_accounts()
    result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
    if not result or "access_token" not in result:
        raise RuntimeError("Outlook token is missing or expired - run `neuranova auth outlook` again")
    _save(cache, cache_file)
    return result["access_token"]


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _graph_time(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class OutlookConnector:
    name = "outlook"

    def __init__(self, token: str, http: httpx.Client | None = None):
        self.http = http or httpx.Client(timeout=30)
        self.headers = {"Authorization": f"Bearer {token}"}

    def _pages(self, url: str, params: dict, limit: int) -> list[dict]:
        items: list[dict] = []
        while url and len(items) < limit:
            resp = self.http.get(url, params=params, headers=self.headers)
            resp.raise_for_status()
            body = resp.json()
            items.extend(body.get("value", []))
            url, params = body.get("@odata.nextLink"), None
        return items[:limit]

    def fetch_inbox(self, since: datetime) -> list[EmailMessage]:
        rows = self._pages(
            f"{GRAPH}/me/mailFolders/inbox/messages",
            {
                "$filter": f"receivedDateTime ge {_graph_time(since)}",
                "$select": "id,conversationId,from,subject,bodyPreview,receivedDateTime,webLink",
                "$orderby": "receivedDateTime desc",
                "$top": "50",
            },
            limit=100,
        )
        out = []
        for m in rows:
            addr = (m.get("from") or {}).get("emailAddress") or {}
            sender = f"{addr.get('name', '')} <{addr.get('address', '')}>".strip()
            out.append(EmailMessage(
                source=self.name,
                external_id=m["id"],
                thread_id=m["conversationId"],
                sender=sender,
                subject=m.get("subject") or "(no subject)",
                snippet=m.get("bodyPreview", ""),
                received_at=_parse_dt(m["receivedDateTime"]),
                link=m.get("webLink", ""),
            ))
        return out

    def fetch_body(self, external_id: str) -> str:
        resp = self.http.get(
            f"{GRAPH}/me/messages/{external_id}",
            params={"$select": "uniqueBody,bodyPreview"},
            headers={**self.headers, "Prefer": 'outlook.body-content-type="text"'},
        )
        resp.raise_for_status()
        body = resp.json()
        return ((body.get("uniqueBody") or {}).get("content") or body.get("bodyPreview", "")).strip()

    def send_reply(self, external_id: str, body: str) -> str:
        # `comment` is HTML placed above the quoted original, like replying in Outlook.
        comment = html.escape(body).replace("\n", "<br>")
        resp = self.http.post(f"{GRAPH}/me/messages/{external_id}/reply",
                              json={"comment": comment}, headers=self.headers)
        resp.raise_for_status()
        return external_id

    def latest_replies(self, since: datetime) -> dict[str, datetime]:
        rows = self._pages(
            f"{GRAPH}/me/mailFolders/sentitems/messages",
            {
                "$filter": f"sentDateTime ge {_graph_time(since)}",
                "$select": "conversationId,sentDateTime",
                "$top": "50",
            },
            limit=200,
        )
        replies: dict[str, datetime] = {}
        for m in rows:
            at = _parse_dt(m["sentDateTime"])
            if m["conversationId"] not in replies or at > replies[m["conversationId"]]:
                replies[m["conversationId"]] = at
        return replies
