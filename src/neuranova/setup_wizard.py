"""`neuranova setup`: create or update .env and the timezone in a few questions.

Safe to run again: it keeps everything already in .env, and it never replaces an existing
DASHBOARD_SECRET (that key encrypts the accounts you connected; changing it would lose them).
"""

from __future__ import annotations

import getpass
import re
import secrets
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import dotenv_values

MIN_PASSWORD = 10
# Values older copies of .env.example switched on. They are the built-in defaults anyway, but set in
# .env they would lock the matching fields on the Integrations page, so setup switches them off.
OLD_EXAMPLE_DEFAULTS = {
    "NOTIFY_CHANNEL": "console", "OUTLOOK_TENANT": "common", "WHATSAPP_TEMPLATE_NAME": "neuranova_update",
    "WHATSAPP_TEMPLATE_LANG": "en", "WHATSAPP_API_VERSION": "v22.0",
    "GMAIL_CLIENT_SECRET_FILE": "secrets/gmail_client_secret.json", "GMAIL_TOKEN_FILE": "secrets/gmail_token.json",
    "OUTLOOK_TOKEN_CACHE": "secrets/outlook_token_cache.json",
}
LOCAL_URL = "http://localhost:8080"


class SetupError(ValueError):
    pass


def guess_timezone() -> str:
    """IANA name of this computer's timezone where the OS exposes it (Mac/Linux), else ''."""
    try:
        target = Path("/etc/localtime").resolve()
        match = re.search(r"zoneinfo/(.+)$", str(target))
        if match:
            ZoneInfo(match.group(1))
            return match.group(1)
    except (OSError, ZoneInfoNotFoundError, ValueError):
        pass
    return ""


def check_timezone(name: str) -> str:
    name = name.strip()
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise SetupError(f'"{name}" is not a timezone name. Examples: Asia/Kolkata, Europe/London, America/New_York.') from exc
    return name


def check_email(email: str) -> str:
    email = email.strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise SetupError("Enter a valid email address.")
    return email


def check_password(password: str) -> str:
    if len(password) < MIN_PASSWORD:
        raise SetupError(f"Use at least {MIN_PASSWORD} characters.")
    return password


def check_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not re.fullmatch(r"https?://[^\s/]+(:\d+)?", url):
        raise SetupError("Enter an address like https://agent.yourdomain.com (no path).")
    return url


def _quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_@.:/+\-]*", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_env(path: Path, updates: dict[str, str | None]) -> None:
    """Set keys in a .env file, keeping every other line (and comments) as they are.
    A value of None removes the key."""
    lines = path.read_text().splitlines() if path.exists() else []
    done = set()
    out = []
    for line in lines:
        match = re.match(r"\s*#?\s*([A-Z][A-Z0-9_]*)\s*=", line)
        key = match.group(1) if match else None
        if key in updates and key not in done:
            commented = line.lstrip().startswith("#")
            if updates[key] is None:
                if not commented:
                    continue
                out.append(line)
            else:
                out.append(f"{key}={_quote(updates[key])}")
            done.add(key)
            continue
        out.append(line)
    for key, value in updates.items():
        if key not in done and value is not None:
            out.append(f"{key}={_quote(value)}")
    path.write_text("\n".join(out).rstrip() + "\n")


def set_timezone(config: Path, tz: str) -> None:
    text = config.read_text() if config.exists() else ""
    if re.search(r'(?m)^timezone\s*=', text):
        text = re.sub(r'(?m)^timezone\s*=\s*"[^"]*"', f'timezone = "{tz}"', text, count=1)
    elif re.search(r"(?m)^\[workspace\]", text):
        text = re.sub(r"(?m)^\[workspace\]\s*$", f'[workspace]\ntimezone = "{tz}"', text, count=1)
    else:
        text += f'\n[workspace]\ntimezone = "{tz}"\n'
    config.write_text(text)


def apply(env_path: Path, config_path: Path, email: str, name: str, password: str, tz: str,
          url: str = LOCAL_URL, example: Path | None = None) -> dict:
    """Validate and write everything. Returns a summary."""
    email, password, tz, url = check_email(email), check_password(password), check_timezone(tz), check_url(url)
    if not name.strip():
        raise SetupError("Enter your name.")
    if not env_path.exists() and example and example.exists():
        env_path.write_text(example.read_text())
    current = dotenv_values(env_path) if env_path.exists() else {}
    kept_secret = bool((current.get("DASHBOARD_SECRET") or "").strip())
    local = url.startswith("http://localhost") or url.startswith("http://127.0.0.1")
    updates: dict[str, str | None] = {
        "OWNER_EMAIL": email,
        "OWNER_NAME": name.strip(),
        "DASHBOARD_PASSWORD": password,
        "PUBLIC_URL": url,
        "DASHBOARD_INSECURE_COOKIE": "1" if local else None,
    }
    if not kept_secret:
        updates["DASHBOARD_SECRET"] = secrets.token_urlsafe(48)
    for key, default in OLD_EXAMPLE_DEFAULTS.items():
        if current.get(key) == default:
            updates[key] = None
    write_env(env_path, updates)
    set_timezone(config_path, tz)
    return {"env": env_path, "kept_secret": kept_secret, "local": local, "url": url, "tz": tz}


def _ask(prompt: str, default: str = "", check=None, secret: bool = False) -> str:
    while True:
        shown = f" [{default}]" if default and not secret else ""
        try:
            value = getpass.getpass(f"{prompt}: ") if secret else input(f"{prompt}{shown}: ")
        except EOFError:
            raise SystemExit("\nSetup cancelled.")
        value = value.strip() or default
        try:
            return check(value) if check else value
        except SetupError as exc:
            print(f"  {exc}")


def run_interactive(env_path: Path = Path(".env"), config_path: Path = Path("neuranova.toml")) -> dict:
    current = dotenv_values(env_path) if env_path.exists() else {}
    print("\nNeuraNova setup\n"
          "Answer a few questions to create your console login. Press Enter to keep the value in [brackets].\n")
    email = _ask("Your email (you sign in with this)", current.get("OWNER_EMAIL") or "", check_email)
    name = _ask("Your name (teammates see this)", current.get("OWNER_NAME") or "")
    while True:
        password = _ask(f"Choose a console password (at least {MIN_PASSWORD} characters)", secret=True,
                        check=check_password)
        if _ask("Type it again", secret=True) == password:
            break
        print("  The two passwords don't match. Try again.")
    config_text = config_path.read_text() if config_path.exists() else ""
    current_tz = re.search(r'(?m)^timezone\s*=\s*"([^"]+)"', config_text)
    tz_default = guess_timezone() or (current_tz.group(1) if current_tz and current_tz.group(1) != "UTC" else "")
    tz = _ask("Your timezone (e.g. Asia/Kolkata, Europe/London)", tz_default or "UTC", check_timezone)
    print("\nWhere will the console run?\n  1. On this computer (http://localhost:8080)\n"
          "  2. On a server with its own web address (needed for WhatsApp)")
    where = _ask("Choose 1 or 2", "1")
    url = LOCAL_URL if where != "2" else _ask("Server address, e.g. https://agent.yourdomain.com",
                                              current.get("PUBLIC_URL") or "", check_url)
    summary = apply(env_path, config_path, email, name, password, tz, url, example=Path(".env.example"))
    print(f"\nSaved to {summary['env']} and neuranova.toml (timezone {summary['tz']}).")
    if summary["kept_secret"]:
        print("Your existing DASHBOARD_SECRET was kept, so connected accounts still work.")
    else:
        print("Created a new DASHBOARD_SECRET. Keep the .env file safe: it encrypts your connected accounts.")
    print(f"\nNext: run  neuranova run  and open {summary['url']}, sign in as {email}, then open Integrations.")
    return summary


def main() -> int:
    try:
        run_interactive()
    except KeyboardInterrupt:
        print("\nSetup cancelled. Nothing was changed.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
