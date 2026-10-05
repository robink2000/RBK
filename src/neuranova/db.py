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

CREATE TABLE IF NOT EXISTS drafts (
    id          INTEGER PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    owner_id    TEXT NOT NULL,
    email_id    INTEGER NOT NULL REFERENCES emails(id),
    body        TEXT NOT NULL,
    needs_input TEXT NOT NULL DEFAULT '[]',
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending | sending | sent | skipped | failed
    created_at  TEXT NOT NULL,
    decided_at  TEXT,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS drafts_status ON drafts (owner_id, status);

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    owner_id     TEXT NOT NULL,
    on_date      TEXT NOT NULL,            -- YYYY-MM-DD, local date the thing happened
    kind         TEXT NOT NULL,
    client       TEXT NOT NULL DEFAULT '',
    value        REAL,
    note         TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL,            -- chat | dashboard
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_date ON events (workspace_id, on_date);

CREATE TABLE IF NOT EXISTS chat_log (
    id       INTEGER PRIMARY KEY,
    owner_id TEXT NOT NULL,
    at       TEXT NOT NULL,
    role     TEXT NOT NULL,                -- founder | agent
    text     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inbound_seen (
    message_id TEXT PRIMARY KEY,
    at         TEXT NOT NULL
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

# Columns added after Phase 1; applied to existing databases on startup.
EMAIL_COLUMNS_V2 = {
    "link": "TEXT NOT NULL DEFAULT ''",
    "create_task": "INTEGER NOT NULL DEFAULT 0",
    "task_title": "TEXT NOT NULL DEFAULT ''",
    "task_due": "TEXT NOT NULL DEFAULT ''",
    "task_id": "TEXT",
}


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class Store:
    def __init__(self, path: str | Path, workspace_id: str, owner_id: str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        if str(path) != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")  # webhook and scheduler share the file
        self.conn.executescript(SCHEMA)
        existing = {r["name"] for r in self.conn.execute("PRAGMA table_info(emails)")}
        for name, ddl in EMAIL_COLUMNS_V2.items():
            if name not in existing:
                self.conn.execute(f"ALTER TABLE emails ADD COLUMN {name} {ddl}")
        self.conn.commit()
        self.workspace_id = workspace_id
        self.owner_id = owner_id

    # --- emails -------------------------------------------------------------

    def add_email(self, msg: EmailMessage) -> bool:
        """Insert a message; returns False if it was already stored."""
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO emails
               (workspace_id, owner_id, source, external_id, thread_id, sender, subject, snippet, received_at, link)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.workspace_id, self.owner_id, msg.source, msg.external_id, msg.thread_id,
             msg.sender, msg.subject, msg.snippet, _iso(msg.received_at), msg.link),
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
               suggested_action = ?, create_task = ?, task_title = ?, task_due = ?,
               reply_deadline = ?, triaged_at = ? WHERE id = ? AND owner_id = ?""",
            (t.category, t.priority, int(t.needs_reply), t.summary, t.suggested_action,
             int(t.create_task), t.task_title, t.task_due,
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

    def email(self, email_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM emails WHERE id = ? AND owner_id = ?", (email_id, self.owner_id)
        ).fetchone()

    # --- tasks from email ---------------------------------------------------

    def tasks_to_create(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT * FROM emails WHERE owner_id = ? AND create_task = 1 AND task_id IS NULL
               ORDER BY received_at""",
            (self.owner_id,),
        ).fetchall()

    def set_task_id(self, email_id: int, task_id: str) -> None:
        self.conn.execute("UPDATE emails SET task_id = ? WHERE id = ?", (task_id, email_id))
        self.conn.commit()

    # --- reply drafts -------------------------------------------------------

    def needing_draft(self, since: datetime, limit: int) -> list[sqlite3.Row]:
        """Emails held to the reply promise, still unanswered, with no draft yet."""
        return self.conn.execute(
            """SELECT e.* FROM emails e WHERE e.owner_id = ? AND e.needs_reply = 1 AND e.replied_at IS NULL
               AND e.reply_deadline IS NOT NULL AND e.received_at >= ?
               AND NOT EXISTS (SELECT 1 FROM drafts d WHERE d.email_id = e.id)
               ORDER BY e.reply_deadline LIMIT ?""",
            (self.owner_id, _iso(since), limit),
        ).fetchall()

    def add_draft(self, email_id: int, body: str, needs_input: list[str]) -> int:
        cur = self.conn.execute(
            """INSERT INTO drafts (workspace_id, owner_id, email_id, body, needs_input, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (self.workspace_id, self.owner_id, email_id, body, json.dumps(needs_input),
             _iso(datetime.now(timezone.utc))),
        )
        self.conn.commit()
        return cur.lastrowid

    def draft(self, draft_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """SELECT d.*, e.source, e.external_id, e.thread_id, e.sender, e.subject, e.summary
               FROM drafts d JOIN emails e ON e.id = d.email_id WHERE d.id = ? AND d.owner_id = ?""",
            (draft_id, self.owner_id),
        ).fetchone()

    def pending_drafts(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT d.*, e.sender, e.subject, e.summary, e.reply_deadline FROM drafts d
               JOIN emails e ON e.id = d.email_id
               WHERE d.owner_id = ? AND d.status = 'pending' ORDER BY d.id""",
            (self.owner_id,),
        ).fetchall()

    def update_draft_body(self, draft_id: int, body: str, needs_input: list[str]) -> bool:
        cur = self.conn.execute(
            "UPDATE drafts SET body = ?, needs_input = ? WHERE id = ? AND owner_id = ? AND status = 'pending'",
            (body, json.dumps(needs_input), draft_id, self.owner_id),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def transition_draft(self, draft_id: int, from_status: str, to_status: str, error: str | None = None) -> bool:
        """Atomic status change; returns False if the draft was not in `from_status` (e.g. already sent)."""
        cur = self.conn.execute(
            """UPDATE drafts SET status = ?, decided_at = ?, error = ?
               WHERE id = ? AND owner_id = ? AND status = ?""",
            (to_status, _iso(datetime.now(timezone.utc)), error, draft_id, self.owner_id, from_status),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def close_drafts_for_replied(self) -> int:
        """Pending drafts whose email you already answered yourself are no longer needed."""
        cur = self.conn.execute(
            """UPDATE drafts SET status = 'skipped', decided_at = ?, error = 'replied outside agent'
               WHERE owner_id = ? AND status = 'pending'
               AND email_id IN (SELECT id FROM emails WHERE replied_at IS NOT NULL)""",
            (_iso(datetime.now(timezone.utc)), self.owner_id),
        )
        self.conn.commit()
        return cur.rowcount

    # --- business events (progress tracking) ----------------------------------

    def add_event(self, on_date: str, kind: str, client: str = "", value: float | None = None,
                  note: str = "", source: str = "chat") -> int:
        cur = self.conn.execute(
            """INSERT INTO events (workspace_id, owner_id, on_date, kind, client, value, note, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.workspace_id, self.owner_id, on_date, kind, client, value, note, source,
             _iso(datetime.now(timezone.utc))),
        )
        self.conn.commit()
        return cur.lastrowid

    def events_between(self, start_date: str, end_date: str) -> list[sqlite3.Row]:
        """Events with start_date <= on_date < end_date (workspace-wide, shared with the team later)."""
        return self.conn.execute(
            "SELECT * FROM events WHERE workspace_id = ? AND on_date >= ? AND on_date < ? ORDER BY on_date, id",
            (self.workspace_id, start_date, end_date),
        ).fetchall()

    def recent_events(self, limit: int = 15) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM events WHERE workspace_id = ? ORDER BY on_date DESC, id DESC LIMIT ?",
            (self.workspace_id, limit),
        ).fetchall()

    def delete_event(self, event_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM events WHERE id = ? AND workspace_id = ?", (event_id, self.workspace_id))
        self.conn.commit()
        return cur.rowcount == 1

    def emails_between(self, start: datetime, end: datetime) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT * FROM emails WHERE owner_id = ? AND triaged_at IS NOT NULL
               AND received_at >= ? AND received_at < ? ORDER BY received_at""",
            (self.owner_id, _iso(start), _iso(end)),
        ).fetchall()

    def search_emails(self, text: str, limit: int = 10) -> list[sqlite3.Row]:
        like = f"%{text}%"
        return self.conn.execute(
            """SELECT * FROM emails WHERE owner_id = ? AND triaged_at IS NOT NULL
               AND (sender LIKE ? OR subject LIKE ? OR summary LIKE ?)
               ORDER BY received_at DESC LIMIT ?""",
            (self.owner_id, like, like, like, limit),
        ).fetchall()

    def recent_activity(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM activity_log WHERE owner_id = ? ORDER BY id DESC LIMIT ?", (self.owner_id, limit)
        ).fetchall()

    # --- chat memory ------------------------------------------------------------

    def add_chat(self, role: str, text: str) -> None:
        self.conn.execute("INSERT INTO chat_log (owner_id, at, role, text) VALUES (?, ?, ?, ?)",
                          (self.owner_id, _iso(datetime.now(timezone.utc)), role, text))
        self.conn.commit()

    def recent_chat(self, limit: int = 8) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            "SELECT * FROM chat_log WHERE owner_id = ? ORDER BY id DESC LIMIT ?", (self.owner_id, limit)
        ).fetchall()
        return list(reversed(rows))

    # --- inbound WhatsApp ---------------------------------------------------

    def first_time_seen(self, message_id: str) -> bool:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO inbound_seen (message_id, at) VALUES (?, ?)",
            (message_id, _iso(datetime.now(timezone.utc))),
        )
        self.conn.commit()
        return cur.rowcount == 1

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
