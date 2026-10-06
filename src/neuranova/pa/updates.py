"""Tell the founder when a newer NeuraNova PA installer is published.

Checked in the background twice a day (never while a page loads). Only reads the public release list; nothing
about the business is sent. Turn off with NEURANOVA_UPDATE_REPO=off.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone

import httpx

from .. import __version__

log = logging.getLogger(__name__)
KEY = "update_check"
DEFAULT_REPO = "robink2000/RBK"


def _ver(text: str) -> tuple[int, ...]:
    return tuple(int(x) for x in text.split("."))


def check(store, http: httpx.Client | None = None) -> dict | None:
    """Look up the latest release and remember the answer. Returns {"version", "url"} when newer."""
    repo = os.environ.get("NEURANOVA_UPDATE_REPO", DEFAULT_REPO)
    if repo.lower() in ("off", "", "0", "false"):
        return None
    client = http or httpx.Client(timeout=8, headers={"Accept": "application/vnd.github+json",
                                                      "User-Agent": f"NeuraNova-PA/{__version__}"})
    try:
        resp = client.get(f"https://api.github.com/repos/{repo}/releases/tags/latest")
        resp.raise_for_status()
        release = resp.json()
    except Exception as exc:
        log.info("Update check skipped: %s", str(exc)[:120])
        return latest(store)
    found = None
    for asset in release.get("assets", []):
        m = re.fullmatch(r"NeuraNova-PA-Setup-(\d+\.\d+\.\d+)\.exe", asset.get("name", ""))
        if m and (found is None or _ver(m.group(1)) > _ver(found["version"])):   # the newest, whatever the order
            found = {"version": m.group(1), "url": asset.get("browser_download_url", ""),
                     "page": release.get("html_url", "")}
    store.put(KEY, json.dumps({"at": datetime.now(timezone.utc).isoformat(), "found": found}))
    return latest(store)


def latest(store) -> dict | None:
    """The cached answer: the newer release, or None when up to date / unknown."""
    raw = store.get(KEY)
    if not raw:
        return None
    found = json.loads(raw).get("found")
    try:
        if found and _ver(found["version"]) > _ver(__version__):
            return found
    except ValueError:
        return None
    return None
