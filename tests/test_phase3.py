import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from neuranova.assistant import TOOLS, Assistant
from neuranova.charts import bar_chart
from neuranova.commands import handle
from neuranova.config import load_settings
from neuranova.db import Store
from neuranova.jobs import Agent
from neuranova.models import EmailMessage, Task, Triage
from neuranova.progress import compute, weekly_series
from neuranova.server import create_app
from test_jobs import LEAD, FakeBrain, FakeMail, FakeNotifier, FakeTodoist, email, recent


def agent_with(settings, store, mail=None, todoist=None, brain=None):
    return Agent(settings, store, brain or FakeBrain({"Quote": LEAD}), FakeNotifier(),
                 mail=[mail or FakeMail([])], todoist=todoist)


# --- progress -------------------------------------------------------------------

def test_progress_counts_leads_replies_and_events(settings, store):
    mail = FakeMail([email("Quote", "1", recent(30)), email("Quote", "2", recent(20))])
    agent = agent_with(settings, store, mail)
    agent.check_inbox()
    mail.replies = {"t-1": datetime.now(timezone.utc)}               # one answered on time
    agent.check_inbox()
    today = datetime.now(settings.tz).date().isoformat()
    store.add_event(today, "deal_won", "Acme", 50000)
    store.add_event(today, "delivery_on_time", "Acme")
    store.add_event(today, "delivery_late", "Beta")
    store.add_event(today, "feedback_positive", "Acme")

    p = compute(store, settings.tz, days=7)
    assert p["business"]["new_leads"] == 1                           # same sender counted once
    assert p["business"]["deals_won"] == 1 and p["business"]["won_value"] == 50000
    assert p["business"]["status"] == "good"
    assert p["responses"]["on_time"] == 1 and p["responses"]["open"] == 1
    assert p["responses"]["on_time_pct"] == 100
    assert p["quality"]["on_time_pct"] == 50 and p["quality"]["status"] == "critical"

    weeks = weekly_series(store, settings.tz, weeks=8)
    assert len(weeks) == 8 and weeks[-1]["new_leads"] == 1 and weeks[-1]["deals_won"] == 1


def test_chart_geometry():
    c = bar_chart(["a", "b", "c"], [50, None, 100], percent=True)
    assert [b.value for b in c["bars"]] == [50, None, 100]
    assert c["bars"][1].path == ""                                   # no bar for missing data
    assert c["bars"][2].h == 2 * c["bars"][0].h                      # linear scale from a zero baseline
    assert c["last"].value == 100 and "Week of c: 100%" == c["bars"][2].tip


# --- chat ------------------------------------------------------------------------

def block(kind, **kw):
    return SimpleNamespace(type=kind, **kw)


class ScriptedClient:
    """Plays back Claude responses: a tool call, then a final answer."""

    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(json.loads(json.dumps(kwargs["messages"], default=lambda o: o.__dict__)))
        self.tools = kwargs["tools"]
        return self.responses.pop(0)


def test_chat_creates_reminder_with_tool(settings, store):
    todo = FakeTodoist()
    agent = agent_with(settings, store, todoist=todo)
    client = ScriptedClient([
        SimpleNamespace(stop_reason="tool_use", content=[
            block("tool_use", id="tu1", name="add_task",
                  input={"content": "Call Asha", "due": "friday 3pm", "priority": "p1", "description": None})]),
        SimpleNamespace(stop_reason="end_turn", content=[block("text", text="Done - *Call Asha* Friday 3pm.")]),
    ])
    reply = handle(agent, "remind me to call Asha friday 3pm", chat=Assistant(agent, client=client).reply)
    assert reply == "Done - *Call Asha* Friday 3pm."
    assert todo.added == [("Call Asha", "", "friday 3pm", 4)]
    tool_result = client.calls[1][-1]["content"][0]
    assert tool_result["tool_use_id"] == "tu1" and "Call Asha" in tool_result["content"]
    assert [r["role"] for r in store.recent_chat()] == ["founder", "agent>founder"]


def test_chat_logs_event_and_reports_tool_errors(settings, store):
    agent = agent_with(settings, store)                              # no Todoist connected
    client = ScriptedClient([
        SimpleNamespace(stop_reason="tool_use", content=[
            block("tool_use", id="a", name="log_event",
                  input={"kind": "deal_won", "client": "Acme", "value": 200000, "note": None, "date": None}),
            block("tool_use", id="b", name="list_tasks", input={"filter": "today"})]),
        SimpleNamespace(stop_reason="end_turn", content=[block("text", text="Logged. Todoist isn't connected.")]),
    ])
    Assistant(agent, client=client).reply("we won Acme, 2 lakh")
    [event] = store.recent_events()
    assert event["kind"] == "deal_won" and event["value"] == 200000 and event["source"] == "chat"
    results = client.calls[1][-1]["content"]
    assert results[1]["is_error"] is True and "Todoist is not connected" in results[1]["content"]


def test_chat_has_no_email_sending_tool():
    names = {t["name"] for t in TOOLS}
    assert not any("send" in n or "email" in n and n != "search_email" for n in names)
    assert all(t["strict"] and t["input_schema"]["additionalProperties"] is False for t in TOOLS)


def test_sentences_are_not_mistaken_for_draft_commands(settings, store):
    mail = FakeMail([email("Quote", "1", recent())])
    agent = agent_with(settings, store, mail)
    agent.check_inbox()
    heard = []
    chat = lambda t: heard.append(t) or "chat"
    assert handle(agent, "send 1 brochure to Acme tomorrow", chat=chat) == "chat"
    assert handle(agent, "list my tasks for today", chat=chat) == "chat"
    assert handle(agent, "status of the Acme deal?", chat=chat) == "chat"
    assert mail.sent == []                                           # nothing was sent
    assert "✅ Sent" in handle(agent, "send 1", chat=chat)
    assert len(heard) == 3


# --- dashboard ---------------------------------------------------------------------

SECRET = "x" * 40


def dashboard_client(tmp_path):
    env = {"DASHBOARD_PASSWORD": "hunter2-long-password", "DASHBOARD_SECRET": SECRET,
           "DASHBOARD_INSECURE_COOKIE": "1", "NEURANOVA_DB": ":memory:"}
    settings = load_settings(tmp_path / "none.toml", env=env)
    store = Store(":memory:", settings.workspace_id, settings.owner_id)
    mail = FakeMail([email("Quote", "1", recent())])
    agent = agent_with(settings, store, mail, todoist=FakeTodoist(
        [Task("9", "Call <investor>", 4, "2026-01-01", None)]))
    agent.check_inbox()
    return TestClient(create_app(settings, lambda: agent, store=store)), agent, mail


def login(client):
    return client.post("/login", data={"email": "owner", "password": "hunter2-long-password"},
                       follow_redirects=False)


def csrf_of(html):
    return html.split('name="csrf" value="')[1].split('"')[0]


def test_dashboard_requires_login_and_throttles(tmp_path):
    client, _, _ = dashboard_client(tmp_path)
    assert client.get("/", follow_redirects=False).headers["location"] == "/login"
    for _ in range(5):
        assert client.post("/login", data={"email": "owner", "password": "nope"}).status_code == 401
    assert client.post("/login", data={"email": "owner", "password": "hunter2-long-password"}).status_code == 429


def test_dashboard_renders_and_escapes(tmp_path):
    client, _, _ = dashboard_client(tmp_path)
    resp = login(client)
    assert resp.status_code == 303 and "httponly" in resp.headers["set-cookie"].lower()
    page = client.get("/").text
    assert "Develop the business" in page and "Drafts to approve (1)" in page
    assert "Call &lt;investor&gt;" in page and "<investor>" not in page
    assert "Replies on time, by week" in page and "<svg" in page


def test_dashboard_actions_need_csrf_and_send_works(tmp_path):
    client, agent, mail = dashboard_client(tmp_path)
    login(client)
    assert client.post("/drafts/1/send", data={"csrf": "forged"}).status_code == 403
    assert mail.sent == []
    token = csrf_of(client.get("/").text)
    resp = client.post("/drafts/1/send", data={"csrf": token, "body": "Hi Asha,\nEdited.\nBest"},
                       follow_redirects=False)
    assert resp.status_code == 303 and "Sent" in resp.headers["location"].replace("%20", " ")
    assert mail.sent == [("1", "Hi Asha,\nEdited.\nBest")]

    resp = client.post("/events", data={"csrf": token, "kind": "deal_won", "client": "Acme",
                                         "value": "1,50,000", "on_date": "2026-10-01", "note": ""},
                       follow_redirects=False)
    assert resp.status_code == 303
    [e] = agent.store.recent_events()
    assert e["value"] == 150000 and e["source"] == "dashboard"


def test_dashboard_off_without_secret(tmp_path):
    settings = load_settings(tmp_path / "none.toml", env={"NEURANOVA_DB": ":memory:"})
    store = Store(":memory:", settings.workspace_id, settings.owner_id)
    client = TestClient(create_app(settings, lambda: None, store=store))
    assert client.get("/login").status_code == 503
    assert client.get("/", follow_redirects=False).headers["location"] == "/login"


def test_demo_builds_and_signs_in(tmp_path):
    from neuranova.demo import DEMO_EMAIL, DEMO_PASSWORD, build_demo
    settings, store, agent = build_demo(tmp_path / "demo.db")
    client = TestClient(create_app(settings, lambda: agent, store=store))
    assert client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
                       follow_redirects=False).status_code == 303
    page = client.get("/").text
    assert 'Neura<span class="nova">Nova</span>' in page and "Drafts to approve" in page
    logo = client.get("/brand/logo")
    assert logo.headers["content-type"] == "image/png" and logo.content.startswith(b"\x89PNG")


def test_custom_brand_logo_and_safe_colors(tmp_path):
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    cfg = tmp_path / "n.toml"
    cfg.write_text(f'[brand]\nname = "Acme Ops"\naccent = "red;}}body{{display:none"\nlogo = "{logo}"\n')
    env = {"DASHBOARD_PASSWORD": "pw-long-enough", "DASHBOARD_SECRET": "s" * 40, "DASHBOARD_INSECURE_COOKIE": "1",
           "NEURANOVA_DB": ":memory:"}
    settings = load_settings(cfg, env=env)
    assert settings.brand["accent"] == "#6b1fa3"                    # unsafe value rejected
    store = Store(":memory:", settings.workspace_id, settings.owner_id)
    client = TestClient(create_app(settings, lambda: SimpleNamespace(store=store), store=store))
    login_page = client.get("/login").text
    assert "Acme Ops" in login_page and 'src="/brand/logo"' in login_page
    assert client.get("/brand/logo").content.startswith(b"\x89PNG")
