"""Team workspace: people, invites, roles, and team tasks.

Roles:
- admin  - everything, including the founder's inbox, drafts, invites and member management
- member - team tasks, goals and progress, event log; never the founder's mailbox or drafts

Team tasks live in the agent's own database (teammates don't need Todoist). Your personal
Todoist is unchanged and stays private to you.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, time, timedelta, timezone

from .db import Store, row_dt

ROLES = ("admin", "member")
INVITE_DAYS = 7
MIN_PASSWORD = 10


class TeamError(ValueError):
    """A user-facing problem (bad input, not allowed)."""


# --- passwords and tokens --------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(digest.hex(), digest_hex)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def digits(number: str) -> str:
    return re.sub(r"\D", "", number or "")


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise TeamError(f"Password must be at least {MIN_PASSWORD} characters.")


def _check_email(email: str) -> str:
    email = email.strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise TeamError("Enter a valid email address.")
    return email


# --- people ----------------------------------------------------------------------------

def ensure_owner(store: Store, settings) -> None:
    """The founder is always an admin. Their login password comes from DASHBOARD_PASSWORD."""
    password = settings.secret("DASHBOARD_PASSWORD")
    existing = store.user(settings.owner_id)
    new_hash = None
    # Skip the (deliberately slow) scrypt check when the env password hasn't changed.
    fingerprint = hashlib.sha256(("owner-pw:" + password).encode()).hexdigest() if password else ""
    if password and not (existing and store.get("owner_pw_fp") == fingerprint):
        if not (existing and verify_password(password, existing["password_hash"])):
            new_hash = hash_password(password)
        store.put("owner_pw_fp", fingerprint)
    store.upsert_user(
        settings.owner_id,
        email=settings.secret("OWNER_EMAIL") or "owner",
        name=settings.secret("OWNER_NAME") or "Founder",
        role="admin",
        password_hash=new_hash,
        whatsapp=digits(settings.secret("WHATSAPP_RECIPIENT")),
    )


def authenticate(store: Store, login: str, password: str):
    user = store.user_by_email(login)
    if user and user["active"] and user["password_hash"] and verify_password(password, user["password_hash"]):
        return user
    return None


def create_invite(store: Store, by_user, email: str, name: str, role: str, whatsapp: str = "") -> str:
    """Returns the one-time token; the caller turns it into a /join/<token> link."""
    if by_user["role"] != "admin":
        raise TeamError("Only admins can invite people.")
    if role not in ROLES:
        raise TeamError("Unknown role.")
    email = _check_email(email)
    if not name.strip():
        raise TeamError("Enter a name.")
    if store.user_by_email(email):
        raise TeamError("Someone with that email is already on the team. Use 'reset link' instead.")
    token = secrets.token_urlsafe(32)
    store.add_invite(token_hash(token), email, name, role, digits(whatsapp), by_user["id"],
                     datetime.now(timezone.utc) + timedelta(days=INVITE_DAYS))
    store.log("invite_created", by=by_user["id"], email=email, role=role)
    return token


def create_reset_link(store: Store, by_user, user_id: str) -> str:
    if by_user["role"] != "admin":
        raise TeamError("Only admins can reset passwords.")
    target = store.user(user_id)
    if target is None or target["id"] == by_user["id"]:
        raise TeamError("Pick another team member.")
    token = secrets.token_urlsafe(32)
    store.add_invite(token_hash(token), target["email"], target["name"], target["role"], target["whatsapp"],
                     by_user["id"], datetime.now(timezone.utc) + timedelta(days=INVITE_DAYS), user_id=target["id"])
    store.log("reset_link_created", by=by_user["id"], user=user_id)
    return token


def accept_invite(store: Store, token: str, password: str) -> str:
    """Create the account (or set a new password) from an invite link. Returns the user id."""
    _check_password(password)
    th = token_hash(token)
    inv = store.invite(th)
    if inv is None or not store.use_invite(th):
        raise TeamError("This link has expired or was already used. Ask your admin for a new one.")
    user_id = inv["user_id"] or "u_" + secrets.token_hex(6)
    if inv["user_id"]:
        store.set_user_fields(user_id, password_hash=hash_password(password), active=1)
    else:
        store.upsert_user(user_id, inv["email"], inv["name"], inv["role"], hash_password(password), inv["whatsapp"])
    store.log("invite_accepted", user=user_id)
    return user_id


def set_active(store: Store, by_user, user_id: str, active: bool) -> None:
    if by_user["role"] != "admin" or user_id == by_user["id"]:
        raise TeamError("Not allowed.")
    store.set_user_fields(user_id, active=int(active))
    store.log("member_active" if active else "member_deactivated", by=by_user["id"], user=user_id)


def find_member(store: Store, name_or_email: str):
    """Match a teammate by email, exact name, or first name (case-insensitive)."""
    q = name_or_email.strip().lower()
    people = store.users()
    for test in (lambda u: u["email"].lower() == q, lambda u: u["name"].lower() == q,
                 lambda u: u["name"].lower().split()[0] == q if u["name"] else False,
                 lambda u: q in u["name"].lower()):
        hits = [u for u in people if test(u)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise TeamError(f"'{name_or_email}' matches {', '.join(h['name'] for h in hits)}. Be more specific.")
    raise TeamError(f"No teammate called '{name_or_email}'. Team: {', '.join(u['name'] for u in people)}.")


# --- tasks --------------------------------------------------------------------------------

def parse_due(value: str | None, tz, end_of_day: time) -> datetime | None:
    """'2026-10-09T15:00' (local) or '2026-10-09' (end of working day) -> aware UTC datetime."""
    if not value or not value.strip():
        return None
    value = value.strip()
    try:
        if "T" in value or " " in value:
            dt = datetime.fromisoformat(value.replace(" ", "T"))
        else:
            dt = datetime.combine(datetime.strptime(value, "%Y-%m-%d").date(), end_of_day)
    except ValueError as exc:
        raise TeamError("Due date must look like 2026-10-09 or 2026-10-09T15:00.") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)


def can_change(user, task) -> bool:
    owner = task["owner_id"] if "owner_id" in task.keys() else task["assignee_id"]
    return user["role"] == "admin" or user["id"] in (owner, task["created_by"])


def format_task(task, tz) -> str:
    due = row_dt(task["due_at"])
    when = f" · due {due.astimezone(tz).strftime('%a %d %b %H:%M')}" if due else ""
    flag = " · BLOCKED" if task["status"] == "blocked" else ""
    keys = task.keys()
    who = (task["owner_name"] if "owner_name" in keys else task["assignee_name"]) or "Unassigned"
    return f"#{task['id']} {task['title']} → {who}{when}{flag}"
