import socket
import threading
import time

import httpx
from dotenv import dotenv_values

from neuranova import launcher


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_first_run_page_health_timezone_and_unicode_name(tmp_path, monkeypatch):
    monkeypatch.setattr("neuranova.setup_wizard.guess_timezone", lambda: "")      # like Windows
    port = free_port()
    result = {}
    t = threading.Thread(target=lambda: result.setdefault("ok", launcher.first_run(tmp_path, port, False)), daemon=True)
    t.start()
    for _ in range(100):
        try:
            health = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).json()
            break
        except httpx.HTTPError:
            time.sleep(0.1)
    assert health["setup"] is True and health["app"] == "neuranova-pa"
    assert launcher.running_version(port) == health["version"]         # a 2nd start sees "same version": opens browser
    page = httpx.get(f"http://127.0.0.1:{port}/").text
    assert 'data-known="0"' in page and "Intl.DateTimeFormat" in page       # the browser fills in the PC's timezone
    r = httpx.post(f"http://127.0.0.1:{port}/", data={"email": "jose@neuranova.in", "name": "José Łukasz", "password": "longpassword1",
                                                      "password2": "longpassword1", "tz": "Asia/Calcutta"})
    assert "Starting NeuraNova PA" in r.text and "/health" in r.text
    t.join(10)
    assert result["ok"] is True
    env = dotenv_values(tmp_path / ".env", encoding="utf-8")
    assert env["OWNER_NAME"] == "José Łukasz" and env["DASHBOARD_PASSWORD"].startswith("scrypt$")
