import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from neuranova.db import Store
from neuranova.pa import qa
from neuranova.pa.store import PAStore

CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
needs_browser = pytest.mark.skipif(not os.path.exists(CHROMIUM) and not os.environ.get("NEURANOVA_CHROMIUM"),
                                   reason="no Chromium available")


def fake_site(state):
    app = FastAPI()
    page = lambda body: HTMLResponse(f"<html><body>{body}</body></html>")  # noqa: E731

    @app.get("/")
    def home():
        return page("<h1>NeuraNova Classroom</h1><a href='/login'>Login</a>")

    @app.get("/login")
    def login_form():
        return page("<form method='post' action='/login'><input type='email' name='email'>"
                    "<input type='password' name='password'><button type='submit'>Log in</button></form>")

    @app.post("/login")
    def login(email: str = Form(...), password: str = Form(...)):
        if password != "right":
            return page("<p>Invalid credentials</p><form method='post'><input type='password' name='password'></form>")
        return RedirectResponse("/dashboard", status_code=303)

    @app.get("/dashboard")
    def dashboard():
        return page("<h2>Dashboard</h2>")

    @app.get("/schedule")
    def schedule():
        broken = state.get("schedule_broken")
        script = "document.getElementById('out').textContent='Class created'" if not broken else \
            "console.error('TypeError: cannot read schedule')"
        return page(f"<button onclick=\"{script}\">Create class</button><p id='out'></p>")

    @app.get("/reports")
    def reports():
        return HTMLResponse("boom", status_code=500)

    return app


@pytest.fixture(scope="module")
def site():
    state = {}
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(fake_site(state), host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}", state
    server.should_exit = True


def browser_factory():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    return pw, pw.chromium.launch(headless=True, executable_path=os.environ.get("NEURANOVA_CHROMIUM", CHROMIUM))


FLOWS = qa.parse_workflows("""
# teacher workflows
[Teacher] Schedule a class (development, production)
goto /schedule
click Create class
expect Class created

[Teacher] Reports page
goto /reports
""")


def test_parse_workflows_and_safe_steps():
    assert [(f.role, f.name, f.environments) for f in FLOWS] == [
        ("Teacher", "Schedule a class", ("development", "production")), ("Teacher", "Reports page", ("development",))]
    assert qa.step_allowed("goto /x", "production") and qa.step_allowed("expect Saved", "production")
    assert not qa.step_allowed("click Delete", "production") and qa.step_allowed("click Delete", "development")
    assert not qa.step_allowed("rm -rf /", "development")


@needs_browser
def test_development_run_records_issues_with_evidence_and_dedupes(site, tmp_path):
    base, state = site
    pa = PAStore(Store(":memory:", "neuranova", "owner"))
    accounts = {"Teacher": {"username": "t@n.in", "password": "right"},
                "Student": {"username": "s@n.in", "password": "wrong"}}
    results = qa.run_environment("development", base, accounts, FLOWS, tmp_path, login_path="/login",
                                 browser_factory=browser_factory, timeout_ms=4000)
    by = {(r.role, r.workflow): r for r in results}
    assert by[("Public", "Availability")].ok
    assert by[("Teacher", "Login")].ok and by[("Teacher", "Schedule a class")].ok
    assert not by[("Student", "Login")].ok and "Login did not succeed" in by[("Student", "Login")].error
    reports = by[("Teacher", "Reports page")]
    assert not reports.ok and "500" in reports.error and Path(reports.screenshot).exists()

    counts = qa.record(pa, results)
    assert counts == {"new": 2, "updated": 0, "regressions": 0, "verified": 0}
    again = qa.run_environment("development", base, accounts, FLOWS, tmp_path, login_path="/login",
                               browser_factory=browser_factory, timeout_ms=4000)
    assert qa.record(pa, again)["updated"] == 2                                # same failures: no duplicates
    assert len(pa.items(kind="qa_issue")) == 2


@needs_browser
def test_production_is_read_only_and_fixes_verify_on_retest(site, tmp_path):
    base, state = site
    pa = PAStore(Store(":memory:", "neuranova", "owner"))
    accounts = {"Teacher": {"username": "t@n.in", "password": "right"}}
    results = qa.run_environment("production", base, accounts, FLOWS, tmp_path, login_path="/login",
                                 browser_factory=browser_factory, timeout_ms=4000)
    flow = next(r for r in results if r.workflow == "Schedule a class")
    assert not flow.ok and "not allowed in Production" in flow.error          # click refused in production

    state["schedule_broken"] = True
    dev = qa.run_environment("development", base, accounts, FLOWS[:1], tmp_path, login_path="/login",
                             browser_factory=browser_factory, timeout_ms=4000)
    failing = next(r for r in dev if r.workflow == "Schedule a class")
    assert not failing.ok and any("cannot read schedule" in c for c in failing.console_errors)
    qa.record(pa, dev)
    [issue] = pa.items(kind="qa_issue")
    assert issue["priority"] == "medium" and "Development" in issue["title"]
    qa.set_stage(pa, issue["id"], "retest", "dev")                            # developer says it's fixed
    assert pa.item(issue["id"])["verification"] == "pending"
    state["schedule_broken"] = False
    fixed = qa.run_environment("development", base, accounts, FLOWS[:1], tmp_path, login_path="/login",
                               browser_factory=browser_factory, timeout_ms=4000)
    assert qa.record(pa, fixed)["verified"] == 1
    row = pa.item(issue["id"])
    assert row["status"] == "verified" and row["verification"] == "passed"
    qa.set_stage(pa, issue["id"], "closed", "qa")
    state["schedule_broken"] = True
    broken_again = qa.run_environment("development", base, accounts, FLOWS[:1], tmp_path, login_path="/login",
                                      browser_factory=browser_factory, timeout_ms=4000)
    assert qa.record(pa, broken_again)["regressions"] == 1
    assert pa.item(issue["id"])["status"] == "open"
