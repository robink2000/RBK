"""Backups: a consistent copy of the database (plus the .env that holds the encryption key) as a zip.

Made automatically once a day and on demand from Settings → Backup. The newest KEEP are kept.
Restore: close NeuraNova PA, unzip a backup into the PA's folder (replacing data/neuranova.db and .env), start it.
"""

from __future__ import annotations

import io
import re
import sqlite3
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

KEEP = 14
NAME = re.compile(r"^neuranova-backup-\d{8}-\d{6}\.zip$")


def folder(settings) -> Path | None:
    db = str(settings.db_path)
    if db == ":memory:":
        return None
    return Path(db).resolve().parent / "backups"


def make(store, settings, env_file: Path | None = None) -> Path | None:
    """Write a backup zip and prune old ones. Returns the new file (None for an in-memory database)."""
    target = folder(settings)
    if target is None:
        return None
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = target / f"neuranova-backup-{stamp}.zip"
    snapshot = target / f".snapshot-{stamp}.db"
    dst = sqlite3.connect(snapshot)
    try:
        store.conn.backup(dst)          # consistent even while the PA is running
    finally:
        dst.close()
    env_file = env_file or _find_env()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(snapshot, "data/neuranova.db")
        if env_file and env_file.is_file():
            z.write(env_file, ".env")
        z.writestr("RESTORE.txt", __doc__ or "")
    snapshot.unlink(missing_ok=True)
    prune(target)
    store.log("backup", file=path.name)
    return path


def _find_env() -> Path | None:
    from dotenv import find_dotenv
    found = find_dotenv(usecwd=True)
    return Path(found) if found else None


def prune(target: Path, keep: int = KEEP) -> None:
    files = sorted(p for p in target.glob("neuranova-backup-*.zip") if NAME.match(p.name))
    for old in files[:-keep]:
        old.unlink(missing_ok=True)


def listing(settings, tz) -> list[dict]:
    target = folder(settings)
    if target is None or not target.exists():
        return []
    out = []
    for p in sorted(target.glob("neuranova-backup-*.zip"), reverse=True):
        if not NAME.match(p.name):
            continue
        made = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).astimezone(tz)
        out.append({"name": p.name, "size": f"{p.stat().st_size / 1024:,.0f} KB", "when": made.strftime("%a %d %b %Y %H:%M")})
    return out


def due(settings) -> bool:
    """True when the newest backup is older than a day (or there is none)."""
    target = folder(settings)
    if target is None:
        return False
    files = sorted(target.glob("neuranova-backup-*.zip")) if target.exists() else []
    if not files:
        return True
    newest = datetime.fromtimestamp(files[-1].stat().st_mtime, timezone.utc)
    return datetime.now(timezone.utc) - newest > timedelta(hours=23)


def path_for(settings, name: str) -> Path | None:
    target = folder(settings)
    if target is None or not NAME.match(name):
        return None
    p = (target / name).resolve()
    return p if p.parent == target.resolve() and p.is_file() else None


def read_db(zip_bytes: bytes) -> bool:
    """Sanity check used by tests and support: the zip holds a readable database."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        return "data/neuranova.db" in z.namelist()
