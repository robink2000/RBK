import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from neuranova.assistant import MEMBER_TOOLS, OWNER_TOOLS, Assistant
from neuranova.commands import handle
from neuranova.config import load_settings
from neuranova.db import Store
from neuranova.jobs import Agent
from neuranova.progress import compute, team_stats
from neuranova.server import create_app
from neuranova.team import (TeamError, accept_invite, authenticate, create_invite, ensure_owner, find_member,
                            hash_password, parse_due, verify_password)
from test_jobs import LEAD, FakeBrain, FakeMail, FakeNotifier, email, recent

OWNER_NUM, PRIYA_NUM = "919999999999", "918888888888"
APP_SECRET = "app-secret"


class Outbox:
    """Collects WhatsApp messages per recipient number."""

    def __init__(self):
        self.by_number = {}

    def factory(self, number):
        return SimpleNamespace(send=lambda text, teaser=None: self.by_number.setdefault(number, []).append(text))


def make_team(tmp_path, extra_env=None):
    env = {"DASHBOARD_PASSWORD": "founder-password-1", "DASHBOARD_SECRET": "s" * 40,
           "DASHBOARD_INSECURE_COOKIE": "1", "OWNER_EMAIL": "robin@neuranova.ai", "OWNER_NAME": "Robin",
           "WHATSAPP_RECIPIENT": "+" + OWNER_NUM, "WHATSAPP_VERIFY_TOKEN": "v", "WHATSAPP_APP_SECRET": APP_SECRET,
           "NEURANOVA_DB": ":memory:", **(extra_env or {})}
    settings = load_settings(tmp_path / "none.toml", env=env)
    store = Store(":memory:", settings.workspace_id, settings.owner_id)
    ensure_owner(store, settings)
    outbox = Outbox()
    mail = FakeMail([email("Quote", "1", recent())])
    agent = Agent(settings, store, FakeBrain({"Quote": LEAD}), FakeNotifier(), mail=[mail],
                  notifier_factory=outbox.factory)
    agent.check_inbox()
    owner = store.user(settings.owner_id)
    token = create_invite(store, owner, "priya@neuranova.ai", "Priya Shah", "member", "+91 88888 88888")
    priya = store.user(accept_invite(store, token, "priya-password-1"))
    return settings, store, agent, owner, priya, outbox, mail


# --- accounts ----------------------------------------------------------------------

def test_passwords_and_owner_account(tmp_path):
    h = hash_password("correct horse battery")
    assert verify_password("correct horse battery", h) and not verify_password("wrong", h)
    settings, store, _, owner, priya, _, _ = make_team(tmp_path)
    assert owner["role"] == "admin" and owner["whatsapp"] == OWNER_NUM and owner["name"] == "Robin"
    assert authenticate(store, "ROBIN@neuranova.ai", "founder-password-1")["id"] == "owner"
    assert authenticate(store, "priya@neuranova.ai", "priya-password-1")["id"] == priya["id"]
    assert authenticate(store, "priya@neuranova.ai", "nope") is None
    assert priya["role"] == "member" and priya["whatsapp"] == PRIYA_NUM


def test_invites_are_single_use_admin_only_and_validated(tmp_path):
    _, store, _, owner, priya, _, _ = make_team(tmp_path)
    with pytest.raises(TeamError, match="Only admins"):
        create_invite(store, priya, "x@y.com", "X", "member")
    with pytest.raises(TeamError, match="already on the team"):
        create_invite(store, owner, "priya@neuranova.ai", "Priya", "member")
    token = create_invite(store, owner, "sam@neuranova.ai", "Sam", "member")
    with pytest.raises(TeamError, match="at least 10"):
        accept_invite(store, token, "short")
    accept_invite(store, token, "sam-password-1")
    with pytest.raises(TeamError, match="expired or was already used"):
        accept_invite(store, token, "sam-password-2")
    assert store.get("invite") is None and len(store.users()) == 3


def test_find_member_and_due_parsing(tmp_path):
    settings, store, _, owner, priya, _, _ = make_team(tmp_path)
    assert find_member(store, "priya")["id"] == priya["id"]
    assert find_member(store, "Priya Shah")["id"] == priya["id"]
    with pytest.raises(TeamError, match="No teammate"):
        find_member(store, "zed")
    assert parse_due("2026-10-09T15:00", settings.tz, settings.working_hours.end) == \
        datetime(2026, 10, 9, 15, tzinfo=timezone.utc)
    assert parse_due("2026-10-09", settings.tz, settings.working_hours.end).hour == 18
    with pytest.raises(TeamError):
        parse_due("friday", settings.tz, settings.working_hours.end)


# --- team tasks ----------------------------------------------------------------------

def test_assign_complete_block_and_permissions(tmp_path):
    settings, store, agent, owner, priya, outbox, _ = make_team(tmp_path)
    task_id = agent.assign_team_task(owner, priya, "Send banner drafts to Acme",
                                     datetime.now(timezone.utc) + timedelta(days=1))
    assert "New task from Robin" in outbox.by_number[PRIYA_NUM][0]

    sam = store.user(accept_invite(store, create_invite(store, owner, "sam@n.ai", "Sam", "member"), "sam-password-1"))
    with pytest.raises(TeamError, match="Only Priya Shah"):
        agent.complete_team_task(sam, task_id)                       # not theirs

    assert "blocked" in agent.block_team_task(priya, task_id, "waiting for logo")
    assert "Priya Shah is blocked" in agent.notifier.sent[-1]        # founder told
    assert agent.complete_team_task(priya, task_id).startswith("✅")
    assert "Priya Shah finished" in agent.notifier.sent[-1]          # creator told
    assert store.team_task(task_id)["status"] == "done"


def test_team_reminders_fire_once(tmp_path):
    settings, store, agent, owner, priya, outbox, _ = make_team(tmp_path)
    now = datetime.now(timezone.utc)
    soon = agent.assign_team_task(owner, priya, "Call Acme", now + timedelta(minutes=10))
    late = agent.assign_team_task(owner, priya, "Invoice Globex", now - timedelta(hours=2))
    outbox.by_number.clear()
    assert agent.team_reminders() == {"reminded": 1, "overdue": 1}
    assert agent.team_reminders() == {"reminded": 0, "overdue": 0}
    msgs = outbox.by_number[PRIYA_NUM]
    assert any(f"#{soon} Call Acme" in m for m in msgs) and any("Overdue" in m and "Invoice Globex" in m for m in msgs)
    assert any("Overdue" in m for m in agent.notifier.sent)          # admin told too


def test_team_stats_and_quality(tmp_path):
    settings, store, agent, owner, priya, _, _ = make_team(tmp_path)
    now = datetime.now(timezone.utc)
    a = agent.assign_team_task(owner, priya, "On time", now + timedelta(hours=5))
    b = agent.assign_team_task(owner, priya, "Late", now - timedelta(hours=5))
    agent.assign_team_task(owner, priya, "Still open", now - timedelta(hours=1))
    agent.complete_team_task(priya, a)
    agent.complete_team_task(priya, b)
    [p] = [s for s in team_stats(store) if s["id"] == priya["id"]]
    assert p == {**p, "open": 1, "overdue": 1, "done": 2, "on_time_pct": 50}
    q = compute(store, settings.tz)["quality"]
    assert q["team_tasks_on_time_pct"] == 50 and q["status"] == "critical"


# --- WhatsApp: members ------------------------------------------------------------------

def test_member_commands_and_no_draft_access(tmp_path):
    settings, store, agent, owner, priya, _, mail = make_team(tmp_path)
    task_id = agent.assign_team_task(owner, priya, "Prep deck")
    chat_calls = []
    chat = lambda t: chat_calls.append(t) or "chat"
    assert f"#{task_id} Prep deck" in handle(agent, "tasks", chat=chat, user=priya)
    assert "Team board" in handle(agent, "team", chat=chat, user=priya)
    assert handle(agent, "send 1", chat=chat, user=priya) == "chat"  # members can't send drafts
    assert handle(agent, "drafts", chat=chat, user=priya) == "chat"
    assert mail.sent == []
    assert handle(agent, f"done {task_id}", chat=chat, user=priya).startswith("✅")
    assert "drafts" not in handle(agent, "help", user=priya)


def test_member_assistant_has_no_mail_or_todoist_tools(tmp_path):
    names = {t["name"] for t in MEMBER_TOOLS}
    assert names == {"assign_task", "team_tasks", "update_team_task", "team_overview", "log_event", "progress"}
    assert {"add_task", "search_email", "waiting_on_me"} <= {t["name"] for t in OWNER_TOOLS}
    settings, store, agent, owner, priya, _, _ = make_team(tmp_path)
    assistant = Assistant(agent, client=object(), user=priya)
    with pytest.raises(ValueError, match="not available"):
        assistant.run_tool("search_email", {"text": "Acme"})
    out = assistant.run_tool("assign_task", {"assignee": "Robin", "title": "Review deck", "due": None, "notes": None})
    assert "Review deck → Robin" in out["created"]


def post_webhook(client, sender, text, msg_id):
    body = json.dumps({"entry": [{"changes": [{"value": {"messages": [
        {"from": sender, "id": msg_id, "type": "text", "text": {"body": text}}]}}]}]}).encode()
    sig = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sig})


def test_webhook_routes_members_by_number(tmp_path):
    settings, store, agent, owner, priya, outbox, _ = make_team(tmp_path)
    task_id = agent.assign_team_task(owner, priya, "Prep deck")
    outbox.by_number.clear()
    client = TestClient(create_app(settings, lambda: agent, store=store))
    post_webhook(client, PRIYA_NUM, f"done {task_id}", "m1")
    assert outbox.by_number[PRIYA_NUM][-1].startswith("✅ Done")     # reply goes to Priya, not the founder
    post_webhook(client, "15550001111", "team", "m2")                # stranger: ignored
    assert store.team_task(task_id)["status"] == "done"
    assert len(outbox.by_number) == 1


# --- dashboard -----------------------------------------------------------------------------

def login(client, email_, password):
    return client.post("/login", data={"email": email_, "password": password}, follow_redirects=False)


def csrf_of(html):
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def test_dashboard_invite_join_and_member_view(tmp_path):
    settings, store, agent, owner, priya, _, mail = make_team(tmp_path)
    admin = TestClient(create_app(settings, lambda: agent, store=store))
    assert login(admin, "robin@neuranova.ai", "founder-password-1").status_code == 303
    token = csrf_of(admin.get("/team").text)
    page = admin.post("/team/invite", data={"csrf": token, "name": "Sam", "email": "sam@n.ai", "role": "member",
                                            "whatsapp": ""}).text
    link = re.search(r'value="(http[^"]+/join/[^"]+)"', page).group(1)
    join_path = link[link.index("/join/"):]

    sam = TestClient(create_app(settings, lambda: agent, store=store))
    assert "Join the team" in sam.get(join_path).text
    assert sam.post(join_path, data={"password": "sam-password-1"}, follow_redirects=False).status_code == 303
    home = sam.get("/").text
    assert "My team tasks" in home and "Drafts to approve" not in home and "Agent activity" not in home
    assert "Waiting for your reply" not in home
    member_csrf = csrf_of(home)
    assert sam.post("/drafts/1/send", data={"csrf": member_csrf}).status_code == 403
    assert mail.sent == []
    assert sam.post("/team/invite", data={"csrf": member_csrf, "name": "X", "email": "x@x.com"}).status_code == 403
    assert "Invite someone" not in sam.get("/team").text
    assert sam.get(join_path).status_code == 404                      # link used up


def test_dashboard_team_task_flow_and_delegation(tmp_path):
    settings, store, agent, owner, priya, outbox, _ = make_team(tmp_path)
    admin = TestClient(create_app(settings, lambda: agent, store=store))
    login(admin, "robin@neuranova.ai", "founder-password-1")
    token = csrf_of(admin.get("/").text)
    resp = admin.post("/team/tasks", data={"csrf": token, "title": "Write case study", "assignee": priya["id"],
                                           "due_date": "2026-12-01", "due_time": "10:30", "notes": ""},
                      follow_redirects=False)
    assert resp.status_code == 303
    [task] = store.team_tasks("open")
    assert task["title"] == "Write case study" and task["due_at"].startswith("2026-12-01T10:30")

    resp = admin.post("/team/tasks/from-email/1", data={"csrf": token, "assignee": priya["id"], "due_date": ""},
                      follow_redirects=False)
    assert "Delegated" in resp.headers["location"].replace("%20", " ")
    delegated = [t for t in store.team_tasks("open") if t["email_id"] == 1][0]
    assert delegated["title"].startswith("Handle email from Asha") and delegated["due_at"]

    board = admin.get("/team").text
    assert "Write case study" in board and "Priya Shah" in board

    member = TestClient(create_app(settings, lambda: agent, store=store))
    login(member, "priya@neuranova.ai", "priya-password-1")
    mtoken = csrf_of(member.get("/team").text)
    resp = member.post(f"/team/tasks/{task['id']}/blocked",
                       data={"csrf": mtoken, "reason": "need brief", "back": "//evil.example"},
                       follow_redirects=False)
    assert resp.headers["location"].startswith("/?msg=")              # off-site redirect refused
    assert store.team_task(task["id"])["status"] == "blocked"


def test_deactivated_member_is_signed_out(tmp_path):
    settings, store, agent, owner, priya, _, _ = make_team(tmp_path)
    member = TestClient(create_app(settings, lambda: agent, store=store))
    login(member, "priya@neuranova.ai", "priya-password-1")
    assert member.get("/", follow_redirects=False).status_code == 200
    store.set_user_fields(priya["id"], active=0)
    assert member.get("/", follow_redirects=False).headers["location"] == "/login"
    assert login(member, "priya@neuranova.ai", "priya-password-1").status_code == 401
