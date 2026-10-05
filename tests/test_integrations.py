import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from neuranova import integrations as integ
from neuranova.server import create_app
from test_team import make_team

FOUNDER = ("robin@neuranova.ai", "founder-password-1")


def csrf_of(html):
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def signed_in(tmp_path, who=FOUNDER, extra_env=None):
    settings, store, agent, owner, priya, _, _ = make_team(tmp_path, extra_env)
    client = TestClient(create_app(settings, lambda: agent, store=store))
    client.post("/login", data={"email": who[0], "password": who[1]})
    return settings, store, client


def test_vault_roundtrip_and_env_precedence(tmp_path):
    settings, store, *_ = make_team(tmp_path, {"TODOIST_API_TOKEN": "from-env"})
    integ.save_values(store, settings, "todoist", {"TODOIST_API_TOKEN": "from-console"}, "owner")
    integ.save_values(store, settings, "claude", {"ANTHROPIC_API_KEY": "sk-ant-console"}, "owner")
    raw = store.integration("claude")["data_enc"]
    assert "sk-ant-console" not in raw                                   # encrypted at rest
    merged = integ.with_integrations(settings, store)
    assert merged.secret("ANTHROPIC_API_KEY") == "sk-ant-console"
    assert merged.secret("TODOIST_API_TOKEN") == "from-env"              # .env wins
    other = integ.Vault("a-different-secret" * 3)
    assert other.open(raw) == {}                                          # wrong key: unreadable, no crash


def test_page_is_founder_only_and_never_shows_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(integ, "test_integration", lambda name, s, store: (True, "Key works.", None))
    settings, store, client = signed_in(tmp_path)
    page = client.get("/integrations").text
    assert "0 of 4 connected" in page and "Connect with Google" in page and "/integrations/google/callback" in page
    token = csrf_of(page)
    resp = client.post("/integrations/claude/save", data={"csrf": token, "ANTHROPIC_API_KEY": "sk-ant-secret-9f2a"},
                       follow_redirects=False)
    assert "Key works" in resp.headers["location"].replace("%20", " ")
    page = client.get("/integrations").text
    assert "sk-ant-secret" not in page and "••••9f2a" in page and "1 of 4 connected" in page
    # a blank secret keeps the saved one
    client.post("/integrations/claude/save", data={"csrf": token, "ANTHROPIC_API_KEY": ""})
    assert integ.with_integrations(settings, store).secret("ANTHROPIC_API_KEY") == "sk-ant-secret-9f2a"
    assert client.post("/integrations/claude/save", data={"csrf": "forged"}).status_code == 403

    _, _, member = signed_in(tmp_path / "m", who=("priya@neuranova.ai", "priya-password-1"))
    assert member.get("/integrations").status_code == 403
    assert "Integrations</a>" not in member.get("/").text


def test_whatsapp_save_generates_verify_token_and_routes_alerts(tmp_path, monkeypatch):
    monkeypatch.setattr(integ, "test_integration", lambda name, s, store: (True, "ready", None))
    settings, store, client = signed_in(tmp_path, extra_env={"WHATSAPP_RECIPIENT": "", "WHATSAPP_VERIFY_TOKEN": "",
                                                              "WHATSAPP_APP_SECRET": ""})
    token = csrf_of(client.get("/integrations").text)
    client.post("/integrations/whatsapp/save", data={
        "csrf": token, "WHATSAPP_PHONE_NUMBER_ID": "123", "WHATSAPP_ACCESS_TOKEN": "EAAG-token",
        "WHATSAPP_RECIPIENT": "+91 98765 43210", "WHATSAPP_APP_SECRET": "appsecret"})
    merged = integ.with_integrations(settings, store)
    assert merged.secret("WHATSAPP_RECIPIENT") == "919876543210"
    assert len(merged.secret("WHATSAPP_VERIFY_TOKEN")) > 20
    assert merged.secret("NOTIFY_CHANNEL") == "whatsapp"
    page = client.get("/integrations").text
    assert merged.secret("WHATSAPP_VERIFY_TOKEN") in page and "/webhook" in page


def test_google_connect_round_trip(tmp_path, monkeypatch):
    settings, store, client = signed_in(tmp_path)
    token = csrf_of(client.get("/integrations").text)
    resp = client.post("/integrations/google/connect", data={"csrf": token}, follow_redirects=False)
    assert "Save your Google client ID" in resp.headers["location"].replace("%20", " ")

    resp = client.post("/integrations/google/connect", data={"csrf": token, "GOOGLE_CLIENT_ID": "cid.apps",
                                                             "GOOGLE_CLIENT_SECRET": "csecret"},
                       follow_redirects=False)
    url = urlparse(resp.headers["location"])
    q = parse_qs(url.query)
    assert url.netloc == "accounts.google.com" and q["redirect_uri"][0].endswith("/integrations/google/callback")
    assert q["access_type"] == ["offline"] and "code_challenge" in q
    state = q["state"][0]

    fake = SimpleNamespace(credentials=SimpleNamespace(to_json=lambda: '{"token": "t", "refresh_token": "r"}'),
                           fetch_token=lambda code: None)
    monkeypatch.setattr(integ, "_google_flow", lambda s, uri, code_verifier=None, scopes=None: fake)
    monkeypatch.setattr(integ, "test_integration", lambda name, s, store: (True, "ok", "robin@gmail.com"))
    bad = TestClient(client.app).get("/integrations/google/callback", params={"state": "forged", "code": "x"})
    assert "expired" in bad.text
    # the callback works without the session cookie (it is SameSite=Strict); the state authorises it
    done = TestClient(client.app).get("/integrations/google/callback", params={"state": state, "code": "abc"})
    assert "Gmail%20connected" in done.text
    assert integ.with_integrations(settings, store).secret("GMAIL_TOKEN_JSON").startswith('{"token"')
    again = TestClient(client.app).get("/integrations/google/callback", params={"state": state, "code": "abc"})
    assert "expired" in again.text                                        # state is single-use
    assert "robin@gmail.com" in client.get("/integrations").text


def test_health_check_alerts_once_when_something_breaks(tmp_path, monkeypatch):
    settings, store, *_ = make_team(tmp_path)
    integ.save_values(store, settings, "todoist", {"TODOIST_API_TOKEN": "tok"}, "owner")
    sent = []
    monkeypatch.setattr(integ, "test_integration", lambda name, s, store: (True, "fine", None))
    integ.health_check(settings, store, sent.append)
    monkeypatch.setattr(integ, "test_integration", lambda name, s, store: (False, "token rejected", None))
    integ.health_check(settings, store, sent.append)
    integ.health_check(settings, store, sent.append)
    assert len(sent) == 1 and "Todoist stopped working: token rejected" in sent[0]


def test_disable_enable_and_expired_states(tmp_path, monkeypatch):
    monkeypatch.setattr(integ, "test_integration", lambda name, s, store: (True, "Key works.", None))
    settings, store, client = signed_in(tmp_path)
    token = csrf_of(client.get("/integrations").text)
    client.post("/integrations/claude/save", data={"csrf": token, "ANTHROPIC_API_KEY": "sk-ant-secret-9f2a"})
    client.post("/integrations/claude/disable", data={"csrf": token})
    assert integ.with_integrations(settings, store).secret("ANTHROPIC_API_KEY") == ""   # kept, but not used
    cards = {c["name"]: c for c in integ.view(settings, store, "http://x")}
    assert cards["claude"]["status"] == "disabled" and "Disabled" in client.get("/integrations").text
    client.post("/integrations/claude/enable", data={"csrf": token})
    assert integ.with_integrations(settings, store).secret("ANTHROPIC_API_KEY") == "sk-ant-secret-9f2a"
    store.set_integration_status("claude", "error", "Token has been expired or revoked.")
    cards = {c["name"]: c for c in integ.view(settings, store, "http://x")}
    assert cards["claude"]["status"] == "expired" and "Expired" in client.get("/integrations").text
    assert client.post("/integrations/claude/disable", data={"csrf": "forged"}).status_code == 403
