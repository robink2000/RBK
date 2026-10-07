"""Storage for NeuraNova PA: work items (+ history), contacts, messages, approvals outbox, reports, QA runs.

Everything lives in the same SQLite file as the rest of the agent and is scoped by workspace.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

from ..db import Store, _iso, row_dt

KINDS = {
    "task": "Task",
    "follow_up": "Follow-up",
    "waiting": "Waiting for",
    "lead": "Lead",
    "qa_issue": "Application issue",
    "quality": "Quality concern",
    "decision": "Decision required",
    "payment": "Payment",
}
DEPARTMENTS = ("Management", "Academics", "Admissions", "Sales", "Teachers", "Students", "Mentors", "Coordinators",
               "Application", "QA", "IT Support", "Marketing", "Payments", "HR", "Operations")
STATUSES = ("new", "open", "in_progress", "waiting", "blocked", "ready_for_retest", "verified", "closed")
STATUS_LABELS = {"new": "New", "open": "Open", "in_progress": "In progress", "waiting": "Waiting", "blocked": "Blocked",
                 "ready_for_retest": "Ready for retest", "verified": "Verified", "closed": "Closed"}
ACTIVE = ("new", "open", "in_progress", "waiting", "blocked", "ready_for_retest")
PRIORITIES = ("urgent", "high", "medium", "low")
PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}

LEAD_STAGES = ("new", "contacted", "demo_pending", "in_progress", "quoted", "payment_pending", "converted", "no_response",
               "lost")
LEAD_STAGE_LABELS = {"new": "New", "contacted": "Contacted", "demo_pending": "Demo pending",
                     "in_progress": "Admission in progress", "quoted": "Quoted", "payment_pending": "Payment pending",
                     "converted": "Converted", "no_response": "No response", "lost": "Lost"}
QA_STAGES = ("new", "assigned", "in_progress", "ready_for_test", "testing", "failed", "fix_required", "retest",
             "verified", "closed")
QA_STAGE_LABELS = {s: s.replace("_", " ").capitalize() for s in QA_STAGES}
QUALITY_CATEGORIES = ("Teaching Quality", "Communication", "Scheduling", "Application", "Payments", "Support", "Staff",
                      "Content", "Admissions")
CONTACT_ROLES = ("parent", "student", "teacher", "mentor", "coordinator", "customer", "staff", "developer",
                 "management", "vendor", "other")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id            INTEGER PRIMARY KEY,
    workspace_id  TEXT NOT NULL,
    kind          TEXT NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    department    TEXT NOT NULL DEFAULT '',
    owner_id      TEXT,
    priority      TEXT NOT NULL DEFAULT 'medium',
    status        TEXT NOT NULL DEFAULT 'open',
    stage         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    due_at        TEXT,
    follow_up_at  TEXT,
    completed_at  TEXT,
    source        TEXT NOT NULL DEFAULT 'manual',
    source_ref    TEXT NOT NULL DEFAULT '',
    source_link   TEXT NOT NULL DEFAULT '',
    waiting_on    TEXT NOT NULL DEFAULT '',
    waiting_since TEXT,
    next_action   TEXT NOT NULL DEFAULT '',
    verification  TEXT NOT NULL DEFAULT '',
    related_person  TEXT NOT NULL DEFAULT '',
    related_project TEXT NOT NULL DEFAULT '',
    contact_id    INTEGER,
    value         REAL,
    data          TEXT NOT NULL DEFAULT '{}',
    fingerprint   TEXT NOT NULL DEFAULT '',
    created_by    TEXT NOT NULL DEFAULT '',
    reminded      INTEGER NOT NULL DEFAULT 0,
    overdue_alerted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS items_active ON items (workspace_id, status, kind);
CREATE INDEX IF NOT EXISTS items_due ON items (workspace_id, due_at);
CREATE INDEX IF NOT EXISTS items_fp ON items (workspace_id, fingerprint);

CREATE TABLE IF NOT EXISTS item_events (
    id       INTEGER PRIMARY KEY,
    item_id  INTEGER NOT NULL REFERENCES items(id),
    at       TEXT NOT NULL,
    actor    TEXT NOT NULL,
    event    TEXT NOT NULL,
    detail   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS item_events_item ON item_events (item_id);

CREATE TABLE IF NOT EXISTS contacts (
    id           INTEGER PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name         TEXT NOT NULL DEFAULT '',
    email        TEXT NOT NULL DEFAULT '',
    phone        TEXT NOT NULL DEFAULT '',
    organization TEXT NOT NULL DEFAULT '',
    role         TEXT NOT NULL DEFAULT 'other',
    notes        TEXT NOT NULL DEFAULT '',
    last_contact_at TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS contacts_email ON contacts (workspace_id, email);
CREATE INDEX IF NOT EXISTS contacts_phone ON contacts (workspace_id, phone);

CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    channel      TEXT NOT NULL,             -- whatsapp | email | note
    direction    TEXT NOT NULL,             -- in | out
    external_id  TEXT NOT NULL,
    thread_key   TEXT NOT NULL DEFAULT '',
    contact_id   INTEGER,
    sender       TEXT NOT NULL DEFAULT '',
    recipient    TEXT NOT NULL DEFAULT '',
    subject      TEXT NOT NULL DEFAULT '',
    body         TEXT NOT NULL DEFAULT '',
    at           TEXT NOT NULL,
    analyzed_at  TEXT,
    summary      TEXT NOT NULL DEFAULT '',
    importance   TEXT NOT NULL DEFAULT '',
    replied_at   TEXT,
    UNIQUE (workspace_id, channel, external_id)
);
CREATE INDEX IF NOT EXISTS messages_at ON messages (workspace_id, at);

CREATE TABLE IF NOT EXISTS outbox (
    id           INTEGER PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    channel      TEXT NOT NULL,             -- whatsapp | email
    recipient    TEXT NOT NULL,
    recipient_name TEXT NOT NULL DEFAULT '',
    subject      TEXT NOT NULL DEFAULT '',
    body         TEXT NOT NULL,
    reason       TEXT NOT NULL DEFAULT '',
    item_id      INTEGER,
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending | sending | sent | rejected | failed
    created_by   TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    decided_by   TEXT NOT NULL DEFAULT '',
    decided_at   TEXT,
    error        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reports (
    id           INTEGER PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    kind         TEXT NOT NULL,
    title        TEXT NOT NULL,
    period_start TEXT,
    period_end   TEXT,
    created_at   TEXT NOT NULL,
    text         TEXT NOT NULL,
    data         TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS reports_kind ON reports (workspace_id, kind, created_at);

CREATE TABLE IF NOT EXISTS qa_runs (
    id           INTEGER PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    environment  TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    status       TEXT NOT NULL DEFAULT 'running',  -- running | passed | failed | error
    summary      TEXT NOT NULL DEFAULT '',
    results      TEXT NOT NULL DEFAULT '[]'
);
"""


def now_iso() -> str:
    return _iso(datetime.now(timezone.utc))


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).strip()


def similarity(a: str, b: str) -> float:
    """Word-overlap similarity (0..1) used to spot duplicate items without an AI call."""
    stop = {"the", "a", "an", "to", "for", "of", "and", "on", "in", "with", "by", "from", "re", "fw", "fwd", "please",
            "about", "regarding", "at", "as", "is", "are", "be", "will", "it", "this", "that", "me", "my", "our", "your",
            "i", "we", "you", "call", "send", "share", "get", "follow", "up", "check", "update", "reply", "mr", "mrs", "ms"}
    wa = {w for w in norm(a).split() if w not in stop}
    wb = {w for w in norm(b).split() if w not in stop}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


class PAStore:
    """PA tables on top of the agent's Store (same connection, same workspace)."""

    ITEM_FIELDS = {"kind", "title", "description", "department", "owner_id", "priority", "status", "stage", "due_at",
                   "follow_up_at", "completed_at", "source", "source_ref", "source_link", "waiting_on",
                   "waiting_since", "next_action", "verification", "related_person", "related_project",
                   "contact_id", "value", "data", "fingerprint", "reminded", "overdue_alerted"}

    def __init__(self, store: Store):
        self.store = store
        self.conn: sqlite3.Connection = store.conn
        self.ws = store.workspace_id
        self.conn.executescript(SCHEMA)
        self._migrate_team_tasks()

    # --- migration from the Phase 4 team board ------------------------------------------------
    def _migrate_team_tasks(self) -> None:
        if self.store.get("pa_migrated_team_tasks"):
            return
        rows = self.conn.execute("SELECT * FROM team_tasks WHERE workspace_id = ?", (self.ws,)).fetchall()
        status_map = {"open": "open", "blocked": "blocked", "done": "closed"}
        for t in rows:
            cur = self.conn.execute(
                """INSERT INTO items (workspace_id, kind, title, description, owner_id, status, created_at, updated_at,
                   due_at, completed_at, source, source_ref, created_by, reminded, overdue_alerted, next_action)
                   VALUES (?, 'task', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.ws, t["title"], t["notes"], t["assignee_id"], status_map.get(t["status"], "open"),
                 t["created_at"], t["created_at"], t["due_at"], t["done_at"],
                 "email" if t["email_id"] else "manual", str(t["email_id"] or ""), t["created_by"], t["reminded"],
                 t["overdue_alerted"], t["blocked_reason"]),
            )
            self._event(cur.lastrowid, "system", "created", "Moved from the team board")
        self.store.put("pa_migrated_team_tasks", "1")
        self.conn.commit()

    # --- items ------------------------------------------------------------------------------------
    def _event(self, item_id: int, actor: str, event: str, detail: str | dict = "") -> None:
        text = json.dumps(detail, default=str) if isinstance(detail, dict) else str(detail)
        self.conn.execute("INSERT INTO item_events (item_id, at, actor, event, detail) VALUES (?, ?, ?, ?, ?)",
                          (item_id, now_iso(), actor, event, text[:2000]))

    @staticmethod
    def _value(v):
        if isinstance(v, datetime):
            return _iso(v)
        if isinstance(v, dict):
            return json.dumps(v, default=str)
        return v

    def create_item(self, actor: str, **fields) -> int:
        fields = {k: self._value(v) for k, v in fields.items() if k in self.ITEM_FIELDS and v is not None}
        fields.setdefault("status", "open")
        now = now_iso()
        cols = ["workspace_id", "created_at", "updated_at", "created_by", *fields]
        cur = self.conn.execute(
            f"INSERT INTO items ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            (self.ws, now, now, actor, *fields.values()),
        )
        self._event(cur.lastrowid, actor, "created", {k: v for k, v in fields.items() if k in ("kind", "title", "source")})
        self.conn.commit()
        return cur.lastrowid

    def update_item(self, item_id: int, actor: str, note: str = "", **fields) -> bool:
        current = self.item(item_id)
        if current is None:
            return False
        changes = {}
        for k, v in fields.items():
            if k not in self.ITEM_FIELDS:
                continue
            v = self._value(v)
            if current[k] != v:
                changes[k] = v
        if not changes and not note:
            return False
        if changes:
            if changes.get("status") in ("closed", "verified") and not current["completed_at"]:
                changes.setdefault("completed_at", now_iso())
            if "status" in changes and changes["status"] in ACTIVE and current["status"] in ("closed", "verified"):
                changes["completed_at"] = None
            if "due_at" in changes:
                changes.update(reminded=0, overdue_alerted=0)
            changes["updated_at"] = now_iso()
            self.conn.execute(
                f"UPDATE items SET {', '.join(f'{k} = ?' for k in changes)} WHERE id = ? AND workspace_id = ?",
                (*changes.values(), item_id, self.ws),
            )
            visible = {k: v for k, v in changes.items() if k not in ("updated_at", "reminded", "overdue_alerted")}
            if visible:
                self._event(item_id, actor, "updated", visible)
        if note:
            self._event(item_id, actor, "note", note)
            if not changes:
                self.conn.execute("UPDATE items SET updated_at = ? WHERE id = ?", (now_iso(), item_id))
        self.conn.commit()
        if changes.get("status") in ("closed", "verified") and current["status"] in ACTIVE:
            from .recurring import follow_on
            follow_on(self, self.item(item_id), actor)
        return True

    def item(self, item_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """SELECT i.*, u.name AS owner_name, u.whatsapp AS owner_whatsapp, c.name AS contact_name
               FROM items i LEFT JOIN users u ON u.id = i.owner_id LEFT JOIN contacts c ON c.id = i.contact_id
               WHERE i.id = ? AND i.workspace_id = ?""",
            (item_id, self.ws),
        ).fetchone()

    def items(self, kind: str | tuple | None = None, status: str | tuple | None = "active", owner_id: str | None = None,
              department: str | None = None, search: str = "", limit: int = 500, order: str = "due") -> list[sqlite3.Row]:
        q = ["""SELECT i.*, u.name AS owner_name, u.whatsapp AS owner_whatsapp, c.name AS contact_name
                FROM items i LEFT JOIN users u ON u.id = i.owner_id LEFT JOIN contacts c ON c.id = i.contact_id
                WHERE i.workspace_id = ?"""]
        args: list = [self.ws]
        if kind:
            kinds = (kind,) if isinstance(kind, str) else tuple(kind)
            q.append(f"AND i.kind IN ({','.join('?' * len(kinds))})")
            args += kinds
        if status == "active":
            q.append(f"AND i.status IN ({','.join('?' * len(ACTIVE))})")
            args += ACTIVE
        elif status:
            statuses = (status,) if isinstance(status, str) else tuple(status)
            q.append(f"AND i.status IN ({','.join('?' * len(statuses))})")
            args += statuses
        if owner_id == "__none__":
            q.append("AND (i.owner_id IS NULL OR i.owner_id = '')")
        elif owner_id:
            q.append("AND i.owner_id = ?")
            args.append(owner_id)
        if department:
            q.append("AND i.department = ?")
            args.append(department)
        if search:
            q.append("AND (i.title LIKE ? OR i.description LIKE ? OR i.related_person LIKE ? OR i.waiting_on LIKE ?)")
            args += [f"%{search}%"] * 4
        q.append({"due": "ORDER BY i.due_at IS NULL, i.due_at, i.id",
                  "recent": "ORDER BY i.updated_at DESC",
                  "created": "ORDER BY i.created_at DESC"}[order])
        q.append("LIMIT ?")
        args.append(limit)
        return self.conn.execute(" ".join(q), args).fetchall()

    def item_events(self, item_id: int) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM item_events WHERE item_id = ? ORDER BY id", (item_id,)).fetchall()

    def find_by_fingerprint(self, fingerprint: str, include_closed: bool = True) -> sqlite3.Row | None:
        if not fingerprint:
            return None
        q = "SELECT * FROM items WHERE workspace_id = ? AND fingerprint = ?"
        if not include_closed:
            q += f" AND status IN ({','.join('?' * len(ACTIVE))})"
        return self.conn.execute(q + " ORDER BY id DESC LIMIT 1",
                                 (self.ws, fingerprint, *(() if include_closed else ACTIVE))).fetchone()

    def similar_open(self, title: str, kind: str | None = None, threshold: float = 0.6,
                     person: str = "") -> sqlite3.Row | None:
        best, best_score = None, threshold
        for row in self.items(kind=kind, status="active", limit=1000):
            score = similarity(title, row["title"])
            if person and row["related_person"] and norm(person) == norm(row["related_person"]):
                score += 0.15
            if score >= best_score:
                best, best_score = row, score
        return best

    def items_completed_between(self, start: datetime, end: datetime) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT i.*, u.name AS owner_name FROM items i LEFT JOIN users u ON u.id = i.owner_id
               WHERE i.workspace_id = ? AND i.completed_at >= ? AND i.completed_at <= ?""",
            (self.ws, _iso(start), _iso(end)),
        ).fetchall()

    def items_created_between(self, start: datetime, end: datetime, kind: str | None = None) -> list[sqlite3.Row]:
        q = "SELECT * FROM items WHERE workspace_id = ? AND created_at >= ? AND created_at <= ?"
        args = [self.ws, _iso(start), _iso(end)]
        if kind:
            q += " AND kind = ?"
            args.append(kind)
        return self.conn.execute(q, args).fetchall()

    # --- contacts (the PA's memory of people) ---------------------------------------------------------
    def contact_for(self, name: str = "", email: str = "", phone: str = "", role: str = "",
                    organization: str = "") -> int:
        email = (email or "").strip().lower()
        phone = re.sub(r"\D", "", phone or "")
        row = None
        if email:
            row = self.conn.execute("SELECT * FROM contacts WHERE workspace_id = ? AND email = ?",
                                    (self.ws, email)).fetchone()
        if row is None and phone:
            row = self.conn.execute("SELECT * FROM contacts WHERE workspace_id = ? AND phone = ?",
                                    (self.ws, phone)).fetchone()
        now = now_iso()
        if row is None:
            cur = self.conn.execute(
                """INSERT INTO contacts (workspace_id, name, email, phone, organization, role, last_contact_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.ws, name.strip(), email, phone, organization.strip(), role or "other", now, now),
            )
            self.conn.commit()
            return cur.lastrowid
        updates = {"last_contact_at": now}
        if name and not row["name"]:
            updates["name"] = name.strip()
        if role and role != "other" and row["role"] in ("", "other"):
            updates["role"] = role
        if organization and not row["organization"]:
            updates["organization"] = organization.strip()
        if email and not row["email"]:
            updates["email"] = email
        if phone and not row["phone"]:
            updates["phone"] = phone
        self.conn.execute(f"UPDATE contacts SET {', '.join(f'{k} = ?' for k in updates)} WHERE id = ?",
                          (*updates.values(), row["id"]))
        self.conn.commit()
        return row["id"]

    def contact(self, contact_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM contacts WHERE id = ? AND workspace_id = ?",
                                 (contact_id, self.ws)).fetchone()

    def contacts(self, search: str = "", limit: int = 200) -> list[sqlite3.Row]:
        like = f"%{search}%"
        return self.conn.execute(
            """SELECT * FROM contacts WHERE workspace_id = ? AND (name LIKE ? OR email LIKE ? OR phone LIKE ?
               OR organization LIKE ?) ORDER BY last_contact_at DESC LIMIT ?""",
            (self.ws, like, like, like, like, limit),
        ).fetchall()

    def update_contact(self, contact_id: int, **fields) -> None:
        allowed = {k: v for k, v in fields.items() if k in ("name", "email", "phone", "organization", "role", "notes")}
        if allowed:
            self.conn.execute(f"UPDATE contacts SET {', '.join(f'{k} = ?' for k in allowed)} WHERE id = ? AND workspace_id = ?",
                              (*allowed.values(), contact_id, self.ws))
            self.conn.commit()

    # --- messages (WhatsApp from contacts, notes; email lives in the emails table) -----------------------
    def add_message(self, channel: str, direction: str, external_id: str, body: str, at: datetime,
                    sender: str = "", recipient: str = "", subject: str = "", contact_id: int | None = None,
                    thread_key: str = "") -> int | None:
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO messages (workspace_id, channel, direction, external_id, thread_key, contact_id,
               sender, recipient, subject, body, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.ws, channel, direction, external_id, thread_key, contact_id, sender, recipient, subject,
             body[:20000], _iso(at)),
        )
        self.conn.commit()
        return cur.lastrowid if cur.rowcount else None

    def unanalyzed_messages(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT m.*, c.name AS contact_name, c.role AS contact_role FROM messages m
               LEFT JOIN contacts c ON c.id = m.contact_id
               WHERE m.workspace_id = ? AND m.direction = 'in' AND m.analyzed_at IS NULL ORDER BY m.at LIMIT ?""",
            (self.ws, limit),
        ).fetchall()

    def mark_analyzed(self, message_id: int, summary: str, importance: str) -> None:
        self.conn.execute("UPDATE messages SET analyzed_at = ?, summary = ?, importance = ? WHERE id = ?",
                          (now_iso(), summary[:500], importance, message_id))
        self.conn.commit()

    def messages(self, channel: str | None = None, since: datetime | None = None, contact_id: int | None = None,
                 limit: int = 200) -> list[sqlite3.Row]:
        q = ["""SELECT m.*, c.name AS contact_name, c.role AS contact_role FROM messages m
                LEFT JOIN contacts c ON c.id = m.contact_id WHERE m.workspace_id = ?"""]
        args: list = [self.ws]
        if channel:
            q.append("AND m.channel = ?")
            args.append(channel)
        if since:
            q.append("AND m.at >= ?")
            args.append(_iso(since))
        if contact_id:
            q.append("AND m.contact_id = ?")
            args.append(contact_id)
        q.append("ORDER BY m.at DESC LIMIT ?")
        args.append(limit)
        return self.conn.execute(" ".join(q), args).fetchall()

    def awaiting_our_reply(self, older_than: datetime) -> list[sqlite3.Row]:
        """Inbound WhatsApp messages marked important that nobody answered."""
        return self.conn.execute(
            """SELECT m.*, c.name AS contact_name FROM messages m LEFT JOIN contacts c ON c.id = m.contact_id
               WHERE m.workspace_id = ? AND m.direction = 'in' AND m.importance IN ('high', 'medium')
               AND m.replied_at IS NULL AND m.at < ? ORDER BY m.at""",
            (self.ws, _iso(older_than)),
        ).fetchall()

    def mark_thread_replied(self, channel: str, contact_id: int | None, at: datetime) -> None:
        if contact_id is None:
            return
        self.conn.execute(
            """UPDATE messages SET replied_at = ? WHERE workspace_id = ? AND channel = ? AND contact_id = ?
               AND direction = 'in' AND replied_at IS NULL AND at <= ?""",
            (_iso(at), self.ws, channel, contact_id, _iso(at)),
        )
        self.conn.commit()

    # --- outbox (messages that need approval before going out) ---------------------------------------------
    def add_outbox(self, channel: str, recipient: str, body: str, created_by: str, recipient_name: str = "",
                   subject: str = "", reason: str = "", item_id: int | None = None) -> int:
        cur = self.conn.execute(
            """INSERT INTO outbox (workspace_id, channel, recipient, recipient_name, subject, body, reason, item_id,
               created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.ws, channel, recipient, recipient_name, subject, body, reason, item_id, created_by, now_iso()),
        )
        self.conn.commit()
        return cur.lastrowid

    def outbox(self, status: str | None = "pending", limit: int = 100) -> list[sqlite3.Row]:
        q = "SELECT * FROM outbox WHERE workspace_id = ?"
        args: list = [self.ws]
        if status:
            q += " AND status = ?"
            args.append(status)
        return self.conn.execute(q + " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()

    def outbox_item(self, outbox_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM outbox WHERE id = ? AND workspace_id = ?",
                                 (outbox_id, self.ws)).fetchone()

    def transition_outbox(self, outbox_id: int, from_status: str, to_status: str, by: str = "", error: str = "",
                          body: str | None = None) -> bool:
        sets = "status = ?, decided_by = ?, decided_at = ?, error = ?" + (", body = ?" if body is not None else "")
        args = [to_status, by, now_iso(), error[:500]] + ([body] if body is not None else [])
        cur = self.conn.execute(f"UPDATE outbox SET {sets} WHERE id = ? AND workspace_id = ? AND status = ?",
                                (*args, outbox_id, self.ws, from_status))
        self.conn.commit()
        return cur.rowcount == 1

    # --- reports -----------------------------------------------------------------------------------------
    def add_report(self, kind: str, title: str, text: str, data: dict, start: datetime | None = None,
                   end: datetime | None = None) -> int:
        cur = self.conn.execute(
            """INSERT INTO reports (workspace_id, kind, title, period_start, period_end, created_at, text, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.ws, kind, title, _iso(start), _iso(end), now_iso(), text, json.dumps(data, default=str)),
        )
        self.conn.commit()
        return cur.lastrowid

    def reports(self, kind: str | None = None, limit: int = 50) -> list[sqlite3.Row]:
        q = "SELECT * FROM reports WHERE workspace_id = ?"
        args: list = [self.ws]
        if kind:
            q += " AND kind = ?"
            args.append(kind)
        return self.conn.execute(q + " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()

    def report(self, report_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM reports WHERE id = ? AND workspace_id = ?",
                                 (report_id, self.ws)).fetchone()

    # --- QA runs -------------------------------------------------------------------------------------------
    def start_qa_run(self, environment: str) -> int:
        cur = self.conn.execute("INSERT INTO qa_runs (workspace_id, environment, started_at) VALUES (?, ?, ?)",
                                (self.ws, environment, now_iso()))
        self.conn.commit()
        return cur.lastrowid

    def finish_qa_run(self, run_id: int, status: str, summary: str, results: list[dict]) -> None:
        self.conn.execute("UPDATE qa_runs SET finished_at = ?, status = ?, summary = ?, results = ? WHERE id = ?",
                          (now_iso(), status, summary, json.dumps(results, default=str), run_id))
        self.conn.commit()

    def qa_runs(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM qa_runs WHERE workspace_id = ? ORDER BY id DESC LIMIT ?",
                                 (self.ws, limit)).fetchall()


def data_of(row) -> dict:
    try:
        return json.loads(row["data"] or "{}")
    except (TypeError, ValueError):
        return {}


def due_of(row) -> datetime | None:
    return row_dt(row["due_at"]) if row["due_at"] else None
