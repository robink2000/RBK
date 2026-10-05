"""SQLite storage. Every row carries workspace_id and owner_id so a team can share one database later."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import EmailMessage, Triage

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    id              INTEGER PRIMARY KEY,
    workspace_id    TEXT NOT NULL,
    owner_id        TEXT NOT NULL,
    source          TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    thread_id       TEXT NOT NULL,
    sender          TEXT NOT NULL,
    subject         TEXT NOT NULL,
    snippet         TEXT NOT NULL,
    received_at     TEXT NOT NULL,
    category        TEXT,
    priority        TEXT,
    needs_reply     INTEGER,
    summary         TEXT,
    suggested_action TEXT,
    triaged_at      TEXT,
    reply_deadline  TEXT,
    replied_at      TEXT,
    sla_stage       INTEGER NOT NULL DEFAULT 0,   -- 0 none, 1 warned, 2 breached
    alerted_new     INTEGER NOT NULL DEFAULT 0,
    UNIQUE (owner_id, source, external_id)
);
CREATE INDEX IF NOT EXISTS emails_open ON emails (owner_id, needs_reply, replied_at);

CREATE TABLE IF NOT EXISTS kv (
    owner_id TEXT NOT NULL,
    key      TEXT NOT NULL,
    value    TEXT NOT NULL,
    PRIMARY KEY (owner_id, key)
);

CREATE TABLE IF NOT EXISTS reminders_sent (
    owner_id TEXT NOT NULL,
    task_id  TEXT NOT NULL,
    due      TEXT NOT NULL,
    PRIMARY KEY (owner_id, task_id, due)
);

CREATE TABLE IF NOT EXISTS activity_log (
    id           INTEGER PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    owner_id     TEXT NOT NULL,
    at           TEXT NOT NULL,
    action       TEXT NOT NULL,
    detail       TEXT NOT NULL
);
"""


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class Store:
    def __init__(self, path: str | Path, workspace_id: str, owner_id: str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.workspace_id = workspace_id
        self.owner_id = owner_id

    # --- emails -------------------------------------------------------------

    def add_email(self, msg: EmailMessage) -> bool:
        """Insert a message; returns False if it was already stored."""
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO emails
               (workspace_id, owner_id, source, external_id, thread_id, sender, subject, snippet, received_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.workspace_id, self.owner_id, msg.source, msg.external_id, msg.thread_id,
             msg.sender, msg.subject, msg.snippet, _iso(msg.received_at)),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def untriaged(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM emails WHERE owner_id = ? AND triaged_at IS NULL ORDER BY received_at LIMIT ?",
            (self.owner_id, limit),
        ).fetchall()

    def save_triage(self, email_id: int, t: Triage, deadline: datetime | None) -> None:
        self.conn.execute(
            """UPDATE emails SET category = ?, priority = ?, needs_reply = ?, summary = ?,
               suggested_action = ?, reply_deadline = ?, triaged_at = ? WHERE id = ? AND owner_id = ?""",
            (t.category, t.priority, int(t.needs_reply), t.summary, t.suggested_action,
             _iso(deadline), _iso(datetime.now(timezone.utc)), email_id, self.owner_id),
        )
        self.conn.commit()

    def awaiting_reply(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT * FROM emails WHERE owner_id = ? AND needs_reply = 1 AND replied_at IS NULL
               ORDER BY COALESCE(reply_deadline, received_at)""",
            (self.owner_id,),
        ).fetchall()

    def mark_replied(self, source: str, thread_id: str, replied_at: datetime) -> int:
        cur = self.conn.execute(
            """UPDATE emails SET replied_at = ? WHERE owner_id = ? AND source = ? AND thread_id = ?
               AND replied_at IS NULL AND received_at < ?""",
            (_iso(replied_at), self.owner_id, source, thread_id, _iso(replied_at)),
        )
        self.conn.commit()
        return cur.rowcount

    def set_sla_stage(self, email_id: int, stage: int) -> None:
        self.conn.execute("UPDATE emails SET sla_stage = ? WHERE id = ?", (stage, email_id))
        self.conn.commit()

    def unalerted_high_priority(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT * FROM emails WHERE owner_id = ? AND priority = 'high' AND alerted_new = 0
               AND triaged_at IS NOT NULL ORDER BY received_at""",
            (self.owner_id,),
        ).fetchall()

    def mark_alerted(self, email_id: int) -> None:
        self.conn.execute("UPDATE emails SET alerted_new = 1 WHERE id = ?", (email_id,))
        self.conn.commit()

    def received_since(self, since: datetime) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM emails WHERE owner_id = ? AND received_at >= ? AND triaged_at IS NOT NULL ORDER BY received_at",
            (self.owner_id, _iso(since)),
        ).fetchall()

    def response_stats(self, since: datetime) -> dict[str, int]:
        """How many SLA emails since `since` were answered on time, late, or are still open."""
        rows = self.conn.execute(
            """SELECT reply_deadline, replied_at FROM emails WHERE owner_id = ? AND needs_reply = 1
               AND reply_deadline IS NOT NULL AND received_at >= ?""",
            (self.owner_id, _iso(since)),
        ).fetchall()
        now = datetime.now(timezone.utc)
        stats = {"on_time": 0, "late": 0, "open": 0, "overdue": 0}
        for r in rows:
            deadline, replied = _dt(r["reply_deadline"]), _dt(r["replied_at"])
            if replied:
                stats["on_time" if replied <= deadline else "late"] += 1
            else:
                stats["overdue" if now > deadline else "open"] += 1
        return stats

    # --- misc ---------------------------------------------------------------

    def get(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM kv WHERE owner_id = ? AND key = ?", (self.owner_id, key)).fetchone()
        return row["value"] if row else None

    def put(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO kv (owner_id, key, value) VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET value = excluded.value",
            (self.owner_id, key, value),
        )
        self.conn.commit()

    def reminder_sent(self, task_id: str, due: str) -> bool:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO reminders_sent (owner_id, task_id, due) VALUES (?, ?, ?)",
            (self.owner_id, task_id, due),
        )
        self.conn.commit()
        return cur.rowcount == 0  # True if it had already been sent

    def log(self, action: str, **detail) -> None:
        self.conn.execute(
            "INSERT INTO activity_log (workspace_id, owner_id, at, action, detail) VALUES (?, ?, ?, ?, ?)",
            (self.workspace_id, self.owner_id, _iso(datetime.now(timezone.utc)), action,
             json.dumps(detail, default=str)),
        )
        self.conn.commit()


def row_dt(value: str | None) -> datetime | None:
    return _dt(value)
