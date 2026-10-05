import builtins
import getpass

import pytest
from dotenv import dotenv_values

from neuranova.config import load_settings
from neuranova.setup_wizard import SetupError, apply, run_interactive, write_env


def test_setup_writes_env_and_timezone(tmp_path):
    env, cfg, example = tmp_path / ".env", tmp_path / "neuranova.toml", tmp_path / ".env.example"
    example.write_text("# Claude\nANTHROPIC_API_KEY=\n# DASHBOARD_INSECURE_COOKIE=1\nOWNER_EMAIL=\n")
    cfg.write_text('[workspace]\nid = "neuranova"\ntimezone = "UTC"        # comment\n')
    out = apply(env, cfg, "robin@neuranova.in", "Robin K", 'p#ss word "quoted" \\ long', "Asia/Kolkata",
                example=example)
    values = dotenv_values(env)
    assert values["OWNER_EMAIL"] == "robin@neuranova.in" and values["OWNER_NAME"] == "Robin K"
    assert values["DASHBOARD_PASSWORD"] == 'p#ss word "quoted" \\ long'   # special characters survive
    assert len(values["DASHBOARD_SECRET"]) >= 60 and values["DASHBOARD_INSECURE_COOKIE"] == "1"
    assert values["PUBLIC_URL"] == "http://localhost:8080"
    assert "# Claude" in env.read_text()                                    # comments from the example kept
    assert env.read_text().count("OWNER_EMAIL=") == 1
    settings = load_settings(cfg, env=dict(values))
    assert settings.tz.key == "Asia/Kolkata" and out["kept_secret"] is False


def test_rerun_keeps_secret_and_other_keys(tmp_path):
    env, cfg = tmp_path / ".env", tmp_path / "neuranova.toml"
    cfg.write_text("[workspace]\n")
    env.write_text("DASHBOARD_SECRET=keep-me-" + "x" * 40 + "\nTODOIST_API_TOKEN=abc\n")
    out = apply(env, cfg, "a@b.co", "A", "long-enough-pw", "Europe/London", url="https://agent.example.com/")
    values = dotenv_values(env)
    assert out["kept_secret"] and values["DASHBOARD_SECRET"].startswith("keep-me-")
    assert values["TODOIST_API_TOKEN"] == "abc" and values["PUBLIC_URL"] == "https://agent.example.com"
    assert "DASHBOARD_INSECURE_COOKIE" not in values                        # never on a real server
    assert 'timezone = "Europe/London"' in cfg.read_text()


@pytest.mark.parametrize("field, value, error", [
    ("email", "not-an-email", "valid email"),
    ("password", "short", "at least 10"),
    ("tz", "India", "not a timezone"),
    ("url", "agent.example.com", "address like"),
])
def test_setup_rejects_bad_input(tmp_path, field, value, error):
    args = {"email": "a@b.co", "password": "long-enough-pw", "tz": "UTC", "url": "http://localhost:8080"}
    args[field] = value
    with pytest.raises(SetupError, match=error):
        apply(tmp_path / ".env", tmp_path / "n.toml", args["email"], "A", args["password"], args["tz"], args["url"])


def test_interactive_flow_retries_bad_answers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "neuranova.toml").write_text('[workspace]\ntimezone = "UTC"\n')
    answers = iter(["bad", "robin@neuranova.in", "Robin", "Asia/Kolkata", "1"])
    passwords = iter(["short", "long-enough-pw", "different-pw!", "long-enough-pw", "long-enough-pw"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(answers))
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(passwords))
    monkeypatch.setattr("neuranova.setup_wizard.guess_timezone", lambda: "")
    run_interactive(tmp_path / ".env", tmp_path / "neuranova.toml")
    values = dotenv_values(tmp_path / ".env")
    assert values["OWNER_EMAIL"] == "robin@neuranova.in" and values["DASHBOARD_PASSWORD"] == "long-enough-pw"


def test_write_env_removes_and_uncomments(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\n# B=old\nC=3\n")
    write_env(env, {"A": None, "B": "new", "D": "4"})
    assert dotenv_values(env) == {"B": "new", "C": "3", "D": "4"}


def test_env_file_is_read_from_the_current_folder(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("OWNER_EMAIL=cwd@neuranova.in\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OWNER_EMAIL", raising=False)
    assert load_settings(tmp_path / "missing.toml").secret("OWNER_EMAIL") == "cwd@neuranova.in"


def test_setup_switches_off_old_example_defaults(tmp_path):
    env = tmp_path / ".env"
    env.write_text("NOTIFY_CHANNEL=console\nOUTLOOK_TENANT=organizations\nGMAIL_TOKEN_FILE=secrets/gmail_token.json\n")
    apply(env, tmp_path / "n.toml", "a@b.co", "A", "long-enough-pw", "UTC")
    values = dotenv_values(env)
    assert "NOTIFY_CHANNEL" not in values and "GMAIL_TOKEN_FILE" not in values
    assert values["OUTLOOK_TENANT"] == "organizations"                    # a value you changed is kept
