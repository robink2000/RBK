import hashlib
import hmac
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from neuranova.config import load_settings
from neuranova.db import Store
from neuranova.notify import inbound_key
from neuranova.server import create_app

SECRET = "app-secret"
OWNER = "919999999999"


def setup(tmp_path):
    env = {"WHATSAPP_VERIFY_TOKEN": "verify-me", "WHATSAPP_APP_SECRET": SECRET,
           "WHATSAPP_RECIPIENT": "+" + OWNER, "NEURANOVA_DB": ":memory:"}
    settings = load_settings(tmp_path / "none.toml", env=env)
    store = Store(":memory:", settings.workspace_id, settings.owner_id)
    sent = []
    agent = SimpleNamespace(store=store, settings=settings,
                            notifier=SimpleNamespace(send=lambda t, teaser=None: sent.append(t)))
    app = create_app(settings, lambda: agent, store=store)
    return TestClient(app), store, sent


def post(client, payload, secret=SECRET):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sig,
                                                          "Content-Type": "application/json"})


def inbound(sender, text, msg_id="wamid.1"):
    return {"entry": [{"changes": [{"value": {"messages": [
        {"from": sender, "id": msg_id, "type": "text", "text": {"body": text}}]}}]}]}


def test_verify_handshake(tmp_path):
    client, _, _ = setup(tmp_path)
    ok = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me",
                                        "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    assert client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "nope"}).status_code == 403


def test_rejects_bad_signature(tmp_path):
    client, store, sent = setup(tmp_path)
    assert post(client, inbound(OWNER, "status"), secret="wrong").status_code == 403
    assert sent == [] and store.get(inbound_key(OWNER)) is None


def test_owner_message_runs_command_once(tmp_path):
    client, store, sent = setup(tmp_path)
    assert post(client, inbound(OWNER, "drafts")).status_code == 200
    assert post(client, inbound(OWNER, "drafts")).status_code == 200   # Meta retry, same id
    assert sent == ["No drafts waiting. 🎉"]
    assert store.get(inbound_key(OWNER)) is not None                       # opens the 24h window


def test_contacts_are_recorded_as_data_never_commands(tmp_path):
    client, store, sent = setup(tmp_path)
    payload = inbound("15550001111", "send 1")
    payload["entry"][0]["changes"][0]["value"]["contacts"] = [{"wa_id": "15550001111", "profile": {"name": "Asha"}}]
    assert post(client, payload).status_code == 200
    assert post(client, payload).status_code == 200                       # Meta retry: stored once
    assert sent == [] and store.get(inbound_key(OWNER)) is None            # no command ran, no reply
    [m] = store.pa.messages()
    assert m["body"] == "send 1" and m["direction"] == "in" and m["contact_name"] == "Asha"
