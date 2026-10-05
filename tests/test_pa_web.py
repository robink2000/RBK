"""Every PA page renders for the founder and for a member, and the main flows work in the browser."""

import re

from test_phase3 import csrf_of, dashboard_client, login

PAGES = ["/", "/today", "/tasks", "/business", "/communications", "/qa", "/quality", "/reports", "/assistant",
         "/search?q=fee", "/settings", "/setup"]
SECTIONS = ["general", "apps", "accounts", "ai", "notifications", "scheduler", "security", "audit"]


def signed_in(tmp_path):
    client, agent, mail = dashboard_client(tmp_path)
    resp = login(client)
    return client, agent, mail, resp


def test_first_login_goes_to_setup_then_home(tmp_path):
    client, agent, _, resp = signed_in(tmp_path)
    assert resp.headers["location"] == "/setup"
    page = client.get("/setup").text
    assert "Step 1 of 10" in page and "Skip for now" in page
    token = csrf_of(page)
    for step in range(1, 10):
        r = client.post(f"/setup/{step}", data={"csrf": token, "action": "skip"}, follow_redirects=False)
        assert r.headers["location"] == f"/setup?step={step + 1}"
    r = client.post("/setup/10", data={"csrf": token}, follow_redirects=False)
    assert r.headers["location"].startswith("/?msg=Setup")
    assert "Welcome to NeuraNova PA" not in client.get("/").text
    login(client)
    assert login(client).headers["location"] == "/"


def test_all_pages_render(tmp_path):
    client, _, _, _ = signed_in(tmp_path)
    for path in PAGES:
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert "Safe Mode on" in resp.text, path
    for s in SECTIONS:
        assert client.get(f"/settings?section={s}").status_code == 200, s
    home = client.get("/").text
    assert "Here's what needs attention now" in home or "Nothing needs your attention" in home


def test_tasks_create_dedupe_edit_done(tmp_path):
    client, agent, _, _ = signed_in(tmp_path)
    token = csrf_of(client.get("/tasks").text)
    r = client.post("/tasks", data={"csrf": token, "title": "Send fee structure to Ravi's parents", "kind": "task",
                                    "due": "tomorrow 3pm", "priority": "high", "department": "Admissions"},
                    follow_redirects=False)
    assert "Added" in r.headers["location"].replace("%20", " ")
    [item] = agent.pa.items(kind="task")
    assert item["priority"] == "high" and item["due_at"]
    r = client.post("/tasks", data={"csrf": token, "title": "Send fee structure to Ravi's parents", "kind": "task"},
                    follow_redirects=False)
    assert r.headers["location"].startswith(f"/tasks/{item['id']}") and len(agent.pa.items(kind="task")) == 1
    page = client.get(f"/tasks/{item['id']}").text
    assert "Send fee structure" in page and "History" in page
    client.post(f"/tasks/{item['id']}", data={"csrf": token, "action": "save", "title": "Send fee structure",
                                              "priority": "urgent", "note": "Parents called again"})
    assert agent.pa.item(item["id"])["priority"] == "urgent"
    client.post(f"/tasks/{item['id']}", data={"csrf": token, "action": "done"})
    assert agent.pa.item(item["id"])["status"] == "closed"
    assert "Parents called again" in client.get(f"/tasks/{item['id']}").text
    r = client.post("/tasks", data={"csrf": token, "title": "x", "due": "someday maybe"}, follow_redirects=False)
    assert "Couldn" in r.headers["location"].replace("%27", "'").replace("%20", " ")


def test_lead_and_quality_from_pages(tmp_path):
    client, agent, _, _ = signed_in(tmp_path)
    token = csrf_of(client.get("/business").text)
    client.post("/tasks", data={"csrf": token, "title": "Sharma family - Grade 6 admission", "kind": "lead",
                                "value": "45,000", "back": "/business"})
    [lead] = agent.pa.items(kind="lead")
    assert lead["value"] == 45000
    assert "Sharma family" in client.get("/business").text
    client.post("/tasks", data={"csrf": token, "title": "Class started 20 minutes late", "kind": "quality",
                                "category": "Scheduling", "back": "/quality"})
    page = client.get("/quality").text
    assert "Scheduling (1)" in page and "Class started 20 minutes late" in page


def test_safe_mode_needs_typed_confirmation(tmp_path):
    client, agent, _, _ = signed_in(tmp_path)
    token = csrf_of(client.get("/settings?section=security").text)
    r = client.post("/settings/security", data={"csrf": token}, follow_redirects=False)
    assert "TURN OFF" in r.headers["location"].replace("%20", " ")
    from neuranova.pa import prefs
    assert prefs.safe_mode(agent.store)
    client.post("/settings/security", data={"csrf": token, "confirm": "TURN OFF"})
    assert not prefs.safe_mode(agent.store)
    assert "Safe Mode on" not in client.get("/today").text
    client.post("/settings/security", data={"csrf": token, "safe_mode": "on"})
    assert prefs.safe_mode(agent.store)


def test_settings_save_and_secrets_not_echoed(tmp_path):
    client, agent, _, _ = signed_in(tmp_path)
    token = csrf_of(client.get("/settings").text)
    client.post("/settings/general", data={"csrf": token, "company_name": "NeuraNova", "timezone": "Asia/Kolkata",
                                           "work_start": "09:30", "work_end": "18:30", "day_mon": "on", "day_sat": "on"})
    page = client.get("/settings?section=general").text
    assert "Asia/Kolkata" in page and "09:30" in page
    client.post("/settings/apps", data={"csrf": token, "NEURANOVA_DEV_URL": "https://dev.example.com"})
    client.post("/settings/accounts", data={"csrf": token, "development__Teacher__user": "t1@x.in",
                                            "development__Teacher__pass": "S3cret-pass!"})
    page = client.get("/settings?section=accounts").text
    assert "t1@x.in" in page and "S3cret-pass!" not in page and "password saved" in page
    assert "S3cret-pass!" not in str([dict(r) for r in agent.store.recent_activity(50)])
    r = client.post("/settings/apps", data={"csrf": token, "NEURANOVA_PROD_URL": "ftp://x"}, follow_redirects=False)
    assert "https" in r.headers["location"]
    assert "Settings" in client.get("/settings?section=audit").text


def test_outbox_compose_and_approve(tmp_path, monkeypatch):
    client, agent, _, _ = signed_in(tmp_path)
    token = csrf_of(client.get("/communications").text)
    sent = []
    monkeypatch.setattr(agent, "compose", lambda *a, **k: agent.pa.add_outbox(
        a[0], a[1], "Dear parent, a reminder about the fee.", reason=a[2], created_by=a[3]))
    client.post("/outbox/compose", data={"csrf": token, "channel": "whatsapp", "recipient": "919800000000",
                                         "purpose": "fee reminder"})
    page = client.get("/communications").text
    assert "Dear parent, a reminder about the fee." in page and "Approve &amp; send" in page
    [o] = agent.pa.outbox("pending")
    monkeypatch.setattr(agent, "send_outbox", lambda oid, by, body=None: sent.append((oid, body)) or "Sent.")
    client.post(f"/outbox/{o['id']}/send", data={"csrf": token, "body": "Edited text"})
    assert sent == [(o["id"], "Edited text")]


def test_reports_generate_and_view(tmp_path):
    client, agent, _, _ = signed_in(tmp_path)
    agent.brain.llm = None
    token = csrf_of(client.get("/reports").text)
    r = client.post("/reports/generate", data={"csrf": token, "kind": "eod"}, follow_redirects=False)
    m = re.match(r"/reports/(\d+)", r.headers["location"])
    page = client.get(f"/reports/{m.group(1)}").text
    assert "End-of-Day Summary" in page


def test_member_sees_no_founder_pages(tmp_path):
    client, agent, _, _ = signed_in(tmp_path)
    from neuranova.team import accept_invite, create_invite
    owner = agent.store.user(agent.settings.owner_id)
    token = create_invite(agent.store, owner, "priya@x.in", "Priya", "member")
    accept_invite(agent.store, token, "priya-password-long")
    client.cookies.clear()
    client.post("/login", data={"email": "priya@x.in", "password": "priya-password-long"})
    for path in ["/today", "/tasks", "/business", "/qa", "/quality", "/assistant"]:
        assert client.get(path).status_code == 200, path
    for path in ["/communications", "/reports", "/settings", "/setup"]:
        assert client.get(path).status_code == 403, path
    assert "Communications" not in client.get("/today").text
