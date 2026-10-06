"""Start the packaged program in a clean folder and check it really works: first-run login page, account
creation, sign-in, every main page, a report, and that the password never lands in .env or the log.

    python packaging/smoke_test.py "dist/NeuraNova PA/NeuraNova PA.exe"
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

PORT = 8187
BASE = f"http://127.0.0.1:{PORT}"
PASSWORD = "Smoke-test-pass-123"
PAGES = ["/", "/today", "/tasks", "/business", "/communications", "/qa", "/quality", "/reports", "/assistant",
         "/settings", "/settings?section=security", "/settings?section=audit", "/integrations", "/setup", "/team"]


def wait_for(url: str, seconds: int = 90) -> httpx.Response:
    end = time.time() + seconds
    while time.time() < end:
        try:
            return httpx.get(url, timeout=3)
        except httpx.HTTPError:
            time.sleep(1)
    raise SystemExit(f"FAIL: nothing answered at {url} within {seconds}s")


def main(exe: str) -> int:
    home = Path(tempfile.mkdtemp(prefix="nnpa-smoke-"))
    log = open(home / "smoke.log", "w")
    env = {**os.environ, "NEURANOVA_HOME": str(home / "app")}
    proc = subprocess.Popen([exe, "--no-browser", "--port", str(PORT)], env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        first = wait_for(BASE + "/")
        assert "Welcome to NeuraNova PA" in first.text, "first-run page missing"
        r = httpx.post(BASE + "/", data={"email": "founder@neuranova.in", "name": "Smoke Test", "password": PASSWORD,
                                         "password2": PASSWORD, "tz": "Asia/Kolkata"}, timeout=30)
        assert "Starting NeuraNova PA" in r.text, r.text[:300]
        time.sleep(3)
        assert wait_for(BASE + "/health", 120).json()["ok"] is True
        with httpx.Client(base_url=BASE, timeout=60) as c:
            r = c.post("/login", data={"email": "founder@neuranova.in", "password": PASSWORD})
            assert r.status_code == 303 and r.headers["location"] == "/setup", (r.status_code, r.headers)
            for page in PAGES:
                r = c.get(page)
                assert r.status_code == 200, (page, r.status_code)
                assert "NeuraNova" in r.text, page
                print(f"ok  {page}")
            csrf = c.get("/reports").text.split('name="csrf" value="')[1].split('"')[0]
            r = c.post("/reports/generate", data={"csrf": csrf, "kind": "morning"})
            assert r.status_code == 303 and r.headers["location"].startswith("/reports/"), r.headers
            assert "Morning Brief" in c.get(r.headers["location"].split("?")[0]).text
            print("ok  report generated")
            r = c.post("/tasks", data={"csrf": csrf, "title": "Smoke test task", "kind": "task", "due": "tomorrow 3pm"})
            assert "Smoke test task" in c.get("/tasks").text
            print("ok  task created")
    finally:
        proc.terminate()
        try:
            proc.wait(15)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
    env_text = (home / "app" / ".env").read_text(encoding="utf-8")
    log_text = (home / "smoke.log").read_text(encoding="utf-8", errors="replace")
    assert PASSWORD not in env_text and PASSWORD not in log_text, "password stored or logged in plain text"
    assert "DASHBOARD_PASSWORD" in env_text and "scrypt$" in env_text
    assert (home / "app" / "data" / "neuranova.db").exists()
    print("PASS: packaged NeuraNova PA starts, sets up, serves every page and keeps the password hashed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
