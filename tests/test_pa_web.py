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
        assert "🛡 Safe Mode" in resp.text, path
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
    assert "🛡 Safe Mode" not in client.get("/today").text
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


def test_quick_add_understands_dates_and_snooze(tmp_path):
    client, agent, _, _ = signed_in(tmp_path)
    token = csrf_of(client.get("/tasks").text)
    r = client.post("/tasks/quick", data={"csrf": token, "text": "Call Ravi's parents tomorrow 3pm", "kind": "task"},
                    headers={"referer": "http://testserver/today"}, follow_redirects=False)
    assert r.headers["location"].startswith("/today?msg=Added")              # back where you were
    [item] = agent.pa.items(kind="task")
    assert item["due_at"] and item["owner_id"] == agent.settings.owner_id
    r = client.post("/tasks/quick", data={"csrf": token, "text": "Call Ravi's parents tomorrow 3pm"}, follow_redirects=False)
    assert r.headers["location"].startswith(f"/tasks/{item['id']}")         # not added twice
    client.post("/tasks/quick", data={"csrf": token, "text": "Pay the hosting bill today"})
    [today_item] = [r for r in agent.pa.items(kind="task") if r["id"] != item["id"]]
    before = today_item["due_at"]
    assert before
    client.post(f"/tasks/{today_item['id']}", data={"csrf": token, "action": "snooze"})
    assert agent.pa.item(today_item["id"])["due_at"] > before
    item = today_item
    page = client.get(f"/tasks/{item['id']}").text
    assert "Added as Task" in page and "Moved to tomorrow" in page and "Due →" in page
    tasks = client.get("/tasks").text
    assert "Tomorrow" in tasks and 'class="tick"' in tasks


def test_friendly_errors_and_checklist(tmp_path):
    client, agent, _, _ = signed_in(tmp_path)
    r = client.post("/tasks/quick", data={"csrf": "forged", "text": "x"})
    assert r.status_code == 403 and "session ran out" in r.text and "<html" in r.text
    from neuranova.pa import prefs
    prefs.save(agent.store, {"setup_done": True})
    home = client.get("/").text
    assert "Getting started" in home and "Connect your email" in home
    health = client.get("/health").json()
    assert health["ok"] and health["app"] == "neuranova-pa" and health["version"]


def test_launcher_reads_running_version(monkeypatch):
    from neuranova import launcher

    class Resp:
        def __init__(self, data): self.data = data
        def json(self): return self.data
    import httpx
    monkeypatch.setattr(httpx, "get", lambda *a, **k: Resp({"ok": True, "app": "neuranova-pa", "version": "9.9"}))
    assert launcher.running_version(1) == "9.9"
    monkeypatch.setattr(httpx, "get", lambda *a, **k: Resp({"ok": True}))
    assert launcher.running_version(1) == ""                                  # an older NeuraNova
    monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("no")))
    assert launcher.running_version(1) is None                               # something else


def test_export_backup_and_phone(tmp_path):
    client, agent, _, _ = signed_in(tmp_path)
    token = csrf_of(client.get("/tasks").text)
    client.post("/tasks/quick", data={"csrf": token, "text": "=HYPERLINK(\"http://evil\") every Friday"})
    client.post("/tasks", data={"csrf": token, "title": "Lead with notes", "kind": "lead", "notes": "line one\nline two"})
    r = client.get("/export/tasks.csv")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert "'=HYPERLINK" in r.text and "every Friday" in r.text and '"line one\nline two"' in r.text.replace("\r\n", "\n")
    assert "Lead with notes" in client.get("/export/leads.csv").text
    assert client.get("/export/contacts.csv").status_code == 200
    page = client.get("/settings?section=backup").text
    assert "Backups" in page and "Back up now" in page          # in-memory test db: nothing on disk to back up
    r = client.post("/settings/phone", data={"csrf": token, "lan_access": "on"}, follow_redirects=False)
    assert "Phone access is on" in r.headers["location"].replace("%20", " ")
    from neuranova.pa import prefs
    assert prefs.get(agent.store)["lan_access"] is True
    assert client.get("/backups/../../etc/passwd").status_code in (303, 404)


def test_backup_zip_roundtrip(tmp_path, settings):
    from dataclasses import replace
    from neuranova.db import Store
    from neuranova.pa import backup
    s = replace(settings, db_path=tmp_path / "data" / "neuranova.db")
    (tmp_path / "data").mkdir()
    store = Store(s.db_path, s.workspace_id, s.owner_id)
    store.pa.create_item("owner", kind="task", title="Keep me safe")
    env = tmp_path / ".env"
    env.write_text("DASHBOARD_SECRET=x\n")
    path = backup.make(store, s, env_file=env)
    assert path and backup.read_db(path.read_bytes()) and not backup.due(s)
    import zipfile
    with zipfile.ZipFile(path) as z:
        assert {"data/neuranova.db", ".env", "RESTORE.txt"} <= set(z.namelist())
        z.extract("data/neuranova.db", tmp_path / "restored")
    restored = Store(tmp_path / "restored" / "data" / "neuranova.db", s.workspace_id, s.owner_id)
    assert restored.pa.items()[0]["title"] == "Keep me safe"
    assert [b["name"] for b in backup.listing(s, s.tz)] == [path.name]
    assert backup.path_for(s, "../x.zip") is None


def test_update_notice(tmp_path, monkeypatch):
    client, agent, _, _ = signed_in(tmp_path)
    from neuranova.pa import updates

    class Http:
        def __init__(self, version): self.version = version
        def get(self, url):
            v = self.version
            return type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: {
                "html_url": "https://github.com/x/releases/latest",
                "assets": [{"name": f"NeuraNova-PA-Setup-{v}.exe", "browser_download_url": f"https://dl/{v}.exe"},
                           {"name": "NeuraNova-PA-Setup-0.0.1.exe", "browser_download_url": "https://dl/old.exe"},
                           {"name": "NeuraNova-PA-Setup.exe", "browser_download_url": "https://dl/stable.exe"}]}})()
    monkeypatch.setenv("NEURANOVA_UPDATE_REPO", "x/y")
    assert updates.check(agent.store, Http("99.0.0"))["version"] == "99.0.0"
    assert "New version 99.0.0" in client.get("/today").text
    assert updates.check(agent.store, Http("0.0.1")) is None
    assert "New version" not in client.get("/today").text
