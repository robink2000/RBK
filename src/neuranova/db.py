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

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    workspace_id  TEXT NOT NULL,
    email         TEXT NOT NULL,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL,             -- admin | member
    password_hash TEXT NOT NULL DEFAULT '',
    whatsapp      TEXT NOT NULL DEFAULT '',  -- digits only, for reminders and chat
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    UNIQUE (workspace_id, email)
);

CREATE TABLE IF NOT EXISTS invites (
    token_hash   TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    email        TEXT NOT NULL,
    name         TEXT NOT NULL,
    role         TEXT NOT NULL,
    whatsapp     TEXT NOT NULL DEFAULT '',
    user_id      TEXT,                      -- set for password-reset links
    created_by   TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    used_at      TEXT
);

CREATE TABLE IF NOT EXISTS team_tasks (
    id             INTEGER PRIMARY KEY,
    workspace_id   TEXT NOT NULL,
    title          TEXT NOT NULL,
    notes          TEXT NOT NULL DEFAULT '',
    assignee_id    TEXT NOT NULL REFERENCES users(id),
    created_by     TEXT NOT NULL,
    due_at         TEXT,                     -- UTC ISO, optional
    status         TEXT NOT NULL DEFAULT 'open',   -- open | blocked | done
    blocked_reason TEXT NOT NULL DEFAULT '',
    email_id       INTEGER,                  -- task created from an email
    created_at     TEXT NOT NULL,
    done_at        TEXT,
    reminded       INTEGER NOT NULL DEFAULT 0,
    overdue_alerted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS team_tasks_open ON team_tasks (workspace_id, status, assignee_id);

CREATE TABLE IF NOT EXISTS integrations (
    workspace_id TEXT NOT NULL,
    name         TEXT NOT NULL,             -- gmail | outlook | todoist | whatsapp | claude
    data_enc     TEXT NOT NULL DEFAULT '',  -- encrypted JSON of keys / tokens
    account      TEXT NOT NULL DEFAULT '',  -- what it's connected as, e.g. an email address
    status       TEXT NOT NULL DEFAULT 'not_connected',  -- connected | error | not_connected
    message      TEXT NOT NULL DEFAULT '',
    checked_at   TEXT,
    updated_by   TEXT NOT NULL DEFAULT '',
    updated_at   TEXT,
    PRIMARY KEY (workspace_id, name)
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
    "pa_analyzed_at": "TEXT",
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

    def emails_for_pa(self, limit: int = 10) -> list[sqlite3.Row]:
        """Triaged emails worth a deeper PA look (skips newsletters, notifications and spam)."""
        return self.conn.execute(
            """SELECT * FROM emails WHERE owner_id = ? AND triaged_at IS NOT NULL AND pa_analyzed_at IS NULL
               AND COALESCE(category, '') NOT IN ('newsletter', 'notification', 'spam')
               AND COALESCE(priority, 'low') IN ('high', 'medium') ORDER BY received_at LIMIT ?""",
            (self.owner_id, limit),
        ).fetchall()

    def mark_email_pa(self, email_id: int) -> None:
        self.conn.execute("UPDATE emails SET pa_analyzed_at = ? WHERE id = ?",
                          (_iso(datetime.now(timezone.utc)), email_id))
        self.conn.commit()

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

    def recent_chat(self, limit: int = 8, role_prefix: tuple[str, ...] | None = None) -> list[sqlite3.Row]:
        """Recent chat lines; `role_prefix` keeps one person's conversation separate from others'."""
        if role_prefix:
            marks = ",".join("?" * len(role_prefix))
            rows = self.conn.execute(
                f"SELECT * FROM chat_log WHERE owner_id = ? AND role IN ({marks}) ORDER BY id DESC LIMIT ?",
                (self.owner_id, *role_prefix, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM chat_log WHERE owner_id = ? ORDER BY id DESC LIMIT ?", (self.owner_id, limit)
            ).fetchall()
        return list(reversed(rows))

    # --- team: users -------------------------------------------------------------

    def user(self, user_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM users WHERE id = ? AND workspace_id = ?",
                                 (user_id, self.workspace_id)).fetchone()

    def user_by_email(self, email: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM users WHERE workspace_id = ? AND lower(email) = lower(?)",
                                 (self.workspace_id, email.strip())).fetchone()

    def user_by_whatsapp(self, digits: str) -> sqlite3.Row | None:
        if not digits:
            return None
        return self.conn.execute("SELECT * FROM users WHERE workspace_id = ? AND whatsapp = ? AND active = 1",
                                 (self.workspace_id, digits)).fetchone()

    def users(self, active_only: bool = True) -> list[sqlite3.Row]:
        q = "SELECT * FROM users WHERE workspace_id = ?" + (" AND active = 1" if active_only else "")
        return self.conn.execute(q + " ORDER BY role, name", (self.workspace_id,)).fetchall()

    def upsert_user(self, user_id: str, email: str, name: str, role: str, password_hash: str | None = None,
                    whatsapp: str | None = None) -> None:
        existing = self.user(user_id)
        if existing is None:
            self.conn.execute(
                """INSERT INTO users (id, workspace_id, email, name, role, password_hash, whatsapp, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, self.workspace_id, email.strip(), name.strip(), role, password_hash or "",
                 whatsapp or "", _iso(datetime.now(timezone.utc))),
            )
        else:
            self.conn.execute(
                """UPDATE users SET email = ?, name = ?, role = ?, password_hash = COALESCE(?, password_hash),
                   whatsapp = COALESCE(?, whatsapp), active = 1 WHERE id = ? AND workspace_id = ?""",
                (email.strip(), name.strip(), role, password_hash, whatsapp, user_id, self.workspace_id),
            )
        self.conn.commit()

    def set_user_fields(self, user_id: str, **fields) -> None:
        allowed = {"name", "role", "whatsapp", "active", "password_hash"}
        cols = [k for k in fields if k in allowed]
        if not cols:
            return
        self.conn.execute(
            f"UPDATE users SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ? AND workspace_id = ?",
            (*[fields[c] for c in cols], user_id, self.workspace_id),
        )
        self.conn.commit()

    # --- team: invites -------------------------------------------------------------

    def add_invite(self, token_hash: str, email: str, name: str, role: str, whatsapp: str,
                   created_by: str, expires_at: datetime, user_id: str | None = None) -> None:
        self.conn.execute(
            """INSERT INTO invites (token_hash, workspace_id, email, name, role, whatsapp, user_id, created_by, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (token_hash, self.workspace_id, email.strip(), name.strip(), role, whatsapp, user_id, created_by,
             _iso(expires_at)),
        )
        self.conn.commit()

    def invite(self, token_hash: str) -> sqlite3.Row | None:
        return self.conn.execute(
            """SELECT * FROM invites WHERE token_hash = ? AND workspace_id = ? AND used_at IS NULL
               AND expires_at > ?""",
            (token_hash, self.workspace_id, _iso(datetime.now(timezone.utc))),
        ).fetchone()

    def use_invite(self, token_hash: str) -> bool:
        cur = self.conn.execute("UPDATE invites SET used_at = ? WHERE token_hash = ? AND used_at IS NULL",
                                (_iso(datetime.now(timezone.utc)), token_hash))
        self.conn.commit()
        return cur.rowcount == 1

    def open_invites(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT * FROM invites WHERE workspace_id = ? AND used_at IS NULL AND expires_at > ?
               ORDER BY expires_at""",
            (self.workspace_id, _iso(datetime.now(timezone.utc))),
        ).fetchall()

    def revoke_invite(self, token_hash: str) -> None:
        self.conn.execute("DELETE FROM invites WHERE token_hash = ? AND workspace_id = ? AND used_at IS NULL",
                          (token_hash, self.workspace_id))
        self.conn.commit()

    # --- team: tasks (stored as PA work items; these keep the original team-board interface) --------------

    @property
    def pa(self):
        if getattr(self, "_pa", None) is None:
            from .pa.store import PAStore
            self._pa = PAStore(self)
        return self._pa

    @staticmethod
    def _legacy_task(row) -> dict | None:
        if row is None:
            return None
        import json as _json
        data = _json.loads(row["data"] or "{}")
        status = {"closed": "done", "verified": "done", "blocked": "blocked"}.get(row["status"], "open")
        return {**dict(row), "assignee_id": row["owner_id"], "assignee_name": row["owner_name"] or "Unassigned",
                "assignee_whatsapp": row["owner_whatsapp"] or "", "notes": row["description"], "status": status,
                "pa_status": row["status"], "blocked_reason": data.get("blocked_reason", ""),
                "done_at": row["completed_at"],
                "email_id": int(row["source_ref"]) if row["source"] == "email" and str(row["source_ref"]).isdigit() else None}

    def add_team_task(self, title: str, assignee_id: str, created_by: str, due_at: datetime | None = None,
                      notes: str = "", email_id: int | None = None, **extra) -> int:
        return self.pa.create_item(created_by, kind=extra.pop("kind", "task"), title=title.strip(),
                                   description=notes.strip(), owner_id=assignee_id, due_at=due_at,
                                   source="email" if email_id else extra.pop("source", "manual"),
                                   source_ref=str(email_id or extra.pop("source_ref", "")), **extra)

    def team_task(self, task_id: int) -> dict | None:
        return self._legacy_task(self.pa.item(task_id))

    def team_tasks(self, status: str | None = "open", assignee_id: str | None = None,
                   limit: int = 200) -> list[dict]:
        """status: 'open' means any active status; 'blocked'; 'done'; None for all."""
        pa_status = {"open": "active", "blocked": "blocked", "done": ("closed", "verified"), None: None}[status]
        rows = self.pa.items(status=pa_status, owner_id=assignee_id, limit=limit)
        rows = [r for r in rows if r["owner_id"]]
        return [self._legacy_task(r) for r in rows]

    def update_team_task(self, task_id: int, actor: str = "agent", **fields) -> bool:
        current = self.pa.item(task_id)
        if current is None:
            return False
        mapped = {}
        for key, value in fields.items():
            if key == "status":
                mapped["status"] = {"done": "closed", "open": "open", "blocked": "blocked"}.get(value, value)
            elif key == "assignee_id":
                mapped["owner_id"] = value
            elif key == "done_at":
                mapped["completed_at"] = value
            elif key == "notes":
                mapped["description"] = value
            elif key == "blocked_reason":
                import json as _json
                data = _json.loads(current["data"] or "{}")
                if value:
                    data["blocked_reason"] = value
                else:
                    data.pop("blocked_reason", None)
                mapped["data"] = data
            else:
                mapped[key] = value
        return self.pa.update_item(task_id, actor, **mapped)

    def team_tasks_done_between(self, start: datetime, end: datetime) -> list[dict]:
        return [self._legacy_task(self.pa.item(r["id"])) for r in self.pa.items_completed_between(start, end)
                if r["owner_id"]]

    # --- integrations ------------------------------------------------------------

    def integration(self, name: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM integrations WHERE workspace_id = ? AND name = ?",
                                 (self.workspace_id, name)).fetchone()

    def integrations(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM integrations WHERE workspace_id = ?",
                                 (self.workspace_id,)).fetchall()

    def save_integration(self, name: str, data_enc: str, updated_by: str) -> None:
        now = _iso(datetime.now(timezone.utc))
        self.conn.execute(
            """INSERT INTO integrations (workspace_id, name, data_enc, updated_by, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (workspace_id, name) DO UPDATE SET data_enc = excluded.data_enc,
               updated_by = excluded.updated_by, updated_at = excluded.updated_at""",
            (self.workspace_id, name, data_enc, updated_by, now),
        )
        self.conn.commit()

    def set_integration_status(self, name: str, status: str, message: str = "", account: str | None = None) -> None:
        self.conn.execute(
            """INSERT INTO integrations (workspace_id, name, status, message, account, checked_at)
               VALUES (?, ?, ?, ?, COALESCE(?, ''), ?)
               ON CONFLICT (workspace_id, name) DO UPDATE SET status = excluded.status,
               message = excluded.message, account = COALESCE(?, integrations.account),
               checked_at = excluded.checked_at""",
            (self.workspace_id, name, status, message[:500], account, _iso(datetime.now(timezone.utc)), account),
        )
        self.conn.commit()

    def delete_integration(self, name: str) -> None:
        self.conn.execute("DELETE FROM integrations WHERE workspace_id = ? AND name = ?", (self.workspace_id, name))
        self.conn.commit()

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
