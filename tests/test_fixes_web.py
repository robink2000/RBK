"""Regression tests for web bugs found in the expert review."""
from neuranova.team import accept_invite, create_invite
from test_phase3 import csrf_of, dashboard_client, login


def founder(tmp_path):
    client, agent, mail = dashboard_client(tmp_path)
    login(client)
    from neuranova.pa import prefs
    prefs.save(agent.store, {"setup_done": True})
    return client, agent, csrf_of(client.get("/tasks").text)


def as_member(client, agent):
    owner = agent.store.user(agent.settings.owner_id)
    accept_invite(agent.store, create_invite(agent.store, owner, "priya@x.in", "Priya", "member"), "priya-password-long")
    client.cookies.clear()
    client.post("/login", data={"email": "priya@x.in", "password": "priya-password-long"})
    return csrf_of(client.get("/tasks").text)


def test_meeting_capture_is_safe(tmp_path):
    client, agent, token = founder(tmp_path)
    r = client.post("/meetings/capture", data={"csrf": token, "uid": "u1", "title": "Parents", "actions": "Send notes",
                                               "due": "blahblah"}, follow_redirects=False)
    assert r.status_code == 303 and "Couldn" in r.headers["location"].replace("%27", "'")
    r = client.post("/meetings/capture", data={"csrf": token, "uid": "u1", "actions": "  \n "}, follow_redirects=False)
    assert "at least one action" in r.headers["location"].replace("%20", " ")
    client.post("/meetings/capture", data={"csrf": token, "uid": "u1", "title": "Parents", "actions": "Send notes", "owner": ""})
    [item] = agent.pa.items(kind="follow_up")
    assert item["owner_id"] == agent.settings.owner_id                 # "Me" really means me


def test_members_cannot_edit_contacts_or_run_qa(tmp_path):
    client, agent, _ = founder(tmp_path)
    cid = agent.pa.contact_for(name="Mrs Sharma", phone="919800000001")
    token = as_member(client, agent)
    assert client.post(f"/contacts/{cid}", data={"csrf": token, "name": "HACKED"}).status_code == 403
    assert agent.pa.contact(cid)["name"] == "Mrs Sharma"
    assert client.post("/qa/run/development", data={"csrf": token}).status_code == 403


def test_task_edit_bugs(tmp_path):
    client, agent, token = founder(tmp_path)
    lead = agent.pa.create_item("owner", kind="lead", title="Sharma admission", stage="new")
    r = client.post(f"/tasks/{lead}", data={"csrf": token, "action": "save", "owner": "ghost"}, follow_redirects=False)
    assert "isn" in r.headers["location"] and agent.pa.item(lead)["owner_id"] is None
    r = client.post(f"/tasks/{lead}", data={"csrf": token, "action": "save", "value": "abc"}, follow_redirects=False)
    assert "number" in r.headers["location"]
    client.post(f"/tasks/{lead}", data={"csrf": token, "action": "save", "stage": "converted"})
    assert agent.pa.item(lead)["status"] == "closed"
    client.post(f"/tasks/{lead}", data={"csrf": token, "action": "save", "stage": "contacted", "status": "closed"})
    assert agent.pa.item(lead)["status"] == "open"                      # back in the pipeline
    assert "Sharma admission" in client.get("/business").text
    r = client.post(f"/tasks/{lead}", data={"csrf": token, "action": "qa_stage", "stage": "verified"}, follow_redirects=False)
    assert "Pick a stage" in r.headers["location"].replace("%20", " ")   # leads have no QA stage
    blocked = agent.pa.create_item("owner", kind="task", title="Print notes", data={"blocked_reason": "printer"})
    page = client.get(f"/tasks/{blocked}").text
    assert 'name="next_action" value=""' in page                       # not pre-filled with the blocked reason


def test_settings_reject_bad_values(tmp_path):
    client, agent, token = founder(tmp_path)
    for data, expect in [({"work_start": "abc", "day_mon": "on"}, "times look like"),
                         ({"work_start": "18:00", "work_end": "09:00", "day_mon": "on"}, "end after"),
                         ({"reply_hours": "abc", "day_mon": "on"}, "Reply promise"),
                         ({}, "working day")]:
        r = client.post("/settings/general", data={"csrf": token, "company_name": "NeuraNova", **data}, follow_redirects=False)
        assert expect in r.headers["location"].replace("%20", " "), (data, r.headers["location"])
    r = client.post("/settings/scheduler", data={"csrf": token, "morning_brief": "99:99"}, follow_redirects=False)
    assert "times look like" in r.headers["location"].replace("%20", " ")


def test_compose_needs_a_real_address_and_bad_params_dont_crash(tmp_path):
    client, agent, token = founder(tmp_path)
    r = client.post("/outbox/compose", data={"csrf": token, "channel": "email", "recipient": "Ravi Parent",
                                             "purpose": "fee reminder"}, follow_redirects=False)
    assert "email address" in r.headers["location"].replace("%20", " ") and not agent.pa.outbox("pending")
    for path in ["/business?days=abc", "/quality?days=x", "/communications?contact=abc", "/?days=zz"]:
        assert client.get(path).status_code == 200, path
