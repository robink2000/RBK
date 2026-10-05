"""Desktop launcher (the Windows "NeuraNova PA" program and Start-menu shortcut).

Double-click → the PA's files live in a per-user folder (%LOCALAPPDATA%\\NeuraNova PA on Windows), the first
time a browser page asks for your login (no terminal questions), then the PA starts and opens in the browser.

    neuranova-pa            start (first-run page if needed)
    neuranova-pa --demo     sample data, nothing connected
    neuranova-pa --no-browser
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

APP_NAME = "NeuraNova PA"
PORT = 8080


def home_dir() -> Path:
    if os.environ.get("NEURANOVA_HOME"):
        return Path(os.environ["NEURANOVA_HOME"])
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / APP_NAME
    return Path.home() / ".neuranova-pa"


def bundled(name: str) -> Path | None:
    """A file shipped next to the program (installer / ZIP) or in the source checkout."""
    roots = [Path(getattr(sys, "_MEIPASS", "")), Path(sys.executable).parent, Path(__file__).resolve().parents[2]]
    for root in roots:
        if root and (root / name).is_file():
            return root / name
    return None


def prepare(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "data").mkdir(exist_ok=True)
    os.chdir(home)
    for name in ("neuranova.toml", ".env.example"):
        if not (home / name).exists() and (src := bundled(name)):
            shutil.copyfile(src, home / name)
    os.environ.setdefault("NEURANOVA_DB", str(home / "data" / "neuranova.db"))


def configured(home: Path) -> bool:
    from dotenv import dotenv_values
    env = dotenv_values(home / ".env") if (home / ".env").exists() else {}
    return bool((env.get("DASHBOARD_PASSWORD") or "").strip() and (env.get("DASHBOARD_SECRET") or "").strip())


def port_busy(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def open_later(url: str, delay: float = 2.5) -> None:
    def go():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Thread(target=go, daemon=True).start()


FIRST_RUN = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Welcome to NeuraNova PA</title><link rel="icon" href="/logo">
<style>body{margin:0;background:#f7f5fa;color:#1a1426;font:15px/1.5 "Segoe UI",system-ui,sans-serif}
.strip{height:4px;background:linear-gradient(90deg,#ee6e1c,#a50f81 50%,#3683c2)}
.card{max-width:440px;margin:8vh auto;background:#fff;border:1px solid rgba(26,20,38,.1);border-radius:12px;padding:24px}
h1{font-size:20px;margin:8px 0}label{display:grid;gap:4px;margin:12px 0;font-weight:600}
input{font:inherit;padding:8px;border:1px solid rgba(26,20,38,.15);border-radius:8px;background:#f7f5fa}
button{font:inherit;background:#6b1fa3;color:#fff;border:0;border-radius:8px;padding:10px 16px;cursor:pointer;width:100%}
.err{color:#d03b3b;font-weight:600}.sub{color:#4f4760;font-size:13px}img{width:48px;height:48px}</style></head>
<body><div class="strip"></div><div class="card"><img src="/logo" alt="NeuraNova logo">
<h1>Welcome to NeuraNova PA</h1><p class="sub">Create your login. Everything stays on this computer; you'll connect email, WhatsApp and AI next, inside the app.</p>
{error}<form method="post" action="/">
<label>Your email<input name="email" type="email" required value="{email}" autocomplete="username"></label>
<label>Your name<input name="name" required value="{name}"></label>
<label>Choose a password (at least 10 characters)<input name="password" type="password" required minlength="10" autocomplete="new-password"></label>
<label>Type it again<input name="password2" type="password" required minlength="10" autocomplete="new-password"></label>
<label>Timezone<input name="tz" required value="{tz}"></label>
<button type="submit">Create login and start</button></form></div></body></html>"""

STARTING = """<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="6;url=/login">
<title>Starting NeuraNova PA</title></head><body style="font-family:system-ui;padding:40px">
<h2>Starting NeuraNova PA…</h2><p>This page opens the sign-in screen in a few seconds. Sign in with the email and password you just chose.</p></body></html>"""


def first_run(home: Path, port: int, browser: bool) -> bool:
    """Serve the one-page login setup until it's completed. Returns True when configured."""
    import html

    import uvicorn
    from fastapi import FastAPI, Form
    from fastapi.responses import HTMLResponse, Response

    from .setup_wizard import SetupError, apply, guess_timezone

    app = FastAPI()
    done = threading.Event()

    def form(error="", email="", name="", tz=""):
        return HTMLResponse(FIRST_RUN.replace("{error}", f'<p class="err">{html.escape(error)}</p>' if error else "")
                            .replace("{email}", html.escape(email)).replace("{name}", html.escape(name))
                            .replace("{tz}", html.escape(tz or guess_timezone() or "Asia/Kolkata")))

    @app.get("/")
    def show():
        return form()

    @app.get("/logo")
    def logo():
        return Response((Path(__file__).parent / "static" / "neuranova-logo.png").read_bytes(), media_type="image/png")

    @app.post("/")
    def save(email: str = Form(""), name: str = Form(""), password: str = Form(""), password2: str = Form(""),
             tz: str = Form("")):
        if password != password2:
            return form("The two passwords don't match.", email, name, tz)
        try:
            apply(home / ".env", home / "neuranova.toml", email, name, password, tz,
                  f"http://localhost:{port}", example=home / ".env.example")
        except SetupError as exc:
            return form(str(exc), email, name, tz)
        done.set()
        return HTMLResponse(STARTING)

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))

    def watch():
        done.wait()
        time.sleep(1.0)  # let the "Starting" page reach the browser
        server.should_exit = True
    threading.Thread(target=watch, daemon=True).start()
    print(f"First run: finish setup in your browser at http://localhost:{port}", flush=True)
    if browser:
        open_later(f"http://localhost:{port}/", 1.5)
    server.run()
    return done.is_set()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="neuranova-pa", description=APP_NAME)
    parser.add_argument("--demo", action="store_true", help="open with sample data")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=int(os.environ.get("WEBHOOK_PORT") or PORT))
    args, rest = parser.parse_known_args(argv)
    home = home_dir()
    prepare(home)
    print(f"{APP_NAME} · files in {home}", flush=True)

    from .cli import main as cli_main
    if rest:                                    # e.g. neuranova-pa report weekly
        return cli_main(rest)
    if port_busy(args.port):
        print(f"{APP_NAME} is already running. Opening it in your browser.", flush=True)
        if not args.no_browser:
            webbrowser.open(f"http://localhost:{args.port}/")
        return 0
    if args.demo:
        return cli_main(["demo", "--port", str(args.port)] + (["--no-browser"] if args.no_browser else []))
    if not configured(home):
        if not first_run(home, args.port, not args.no_browser):
            return 1
    else:
        if not args.no_browser:
            open_later(f"http://localhost:{args.port}/", 4)
    os.environ["WEBHOOK_PORT"] = str(args.port)
    print(f"{APP_NAME} is running at http://localhost:{args.port} — keep this window open (Ctrl+C to stop).",
          flush=True)
    return cli_main(["run"])


if __name__ == "__main__":
    raise SystemExit(main())
