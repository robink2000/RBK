"""Google Drive: save reports as Google Docs in a "NeuraNova PA Reports" folder.

Uses the drive.file permission, so the PA can only see files it created itself.
"""

from __future__ import annotations

import json

FOLDER_NAME = "NeuraNova PA Reports"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _session(token_json: str, on_refresh=None):
    from google.auth.transport.requests import AuthorizedSession, Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_info(json.loads(token_json))
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        if on_refresh:
            on_refresh(creds.to_json())
    return AuthorizedSession(creds)


def account(token_json: str, on_refresh=None) -> str:
    resp = _session(token_json, on_refresh).get("https://www.googleapis.com/drive/v3/about", params={"fields": "user"})
    resp.raise_for_status()
    return resp.json().get("user", {}).get("emailAddress", "")


def upload_report(token_json: str, title: str, text: str, folder_id: str = "", on_refresh=None) -> tuple[str, str]:
    """Create a Google Doc from the report text. Returns (file link, folder id)."""
    session = _session(token_json, on_refresh)
    if not folder_id:
        resp = session.post("https://www.googleapis.com/drive/v3/files",
                            json={"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"})
        resp.raise_for_status()
        folder_id = resp.json()["id"]
    boundary = "neuranova-pa-report"
    meta = json.dumps({"name": title, "mimeType": "application/vnd.google-apps.document", "parents": [folder_id]})
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
            f"--{boundary}\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n{text}\r\n--{boundary}--").encode()
    resp = session.post("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink",
                        data=body, headers={"Content-Type": f"multipart/related; boundary={boundary}"})
    resp.raise_for_status()
    return resp.json().get("webViewLink", ""), folder_id
