"""Desktop launcher (the Windows "NeuraNova PA" program and Start-menu shortcut).

Double-click → the PA's files live in a per-user folder (%LOCALAPPDATA%\\NeuraNova PA on Windows), the first
time a browser page asks for your login (no terminal questions), then the PA starts and opens in the browser.

    neuranova-pa            start (first-run page if needed)
    neuranova-pa --demo     sample data, nothing connected
    neuranova-pa --no-browser
    neuranova-pa --no-tray    run in a console window instead of the system tray (Windows)
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


def running_version(port: int) -> str | None:
    """Version of the NeuraNova PA answering on this port; "" for an older NeuraNova; None for something else."""
    try:
        import httpx
        data = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2).json()
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("ok"):
        return None
    return data.get("version", "") if data.get("app") == "neuranova-pa" or "version" not in data else ""


def open_later(url: str, delay: float = 1.0, wait_for: str = "/health", timeout: float = 120) -> None:
    """Open the browser once the page really answers (a cold start can take a while), never on a dead page."""
    def go():
        time.sleep(delay)
        base = url.split("/", 3)
        probe = f"{base[0]}//{base[2]}{wait_for}"
        end = time.time() + timeout
        while time.time() < end:
            try:
                import httpx
                if httpx.get(probe, timeout=2).status_code < 500:
                    break
            except Exception:
                pass
            time.sleep(0.7)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Thread(target=go, daemon=True).start()


FIRST_RUN = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Welcome to NeuraNova PA</title><link rel="icon" href="/logo">
<style>body{margin:0;min-height:100vh;color:#1a1426;font:15px/1.5 "Segoe UI",system-ui,sans-serif;background:#fdfbff}
body::before{content:"";position:fixed;inset:0;z-index:-1;background:radial-gradient(circle 220px at 50% calc(50% - 300px),rgba(70,140,200,.55) 99%,transparent 100%),radial-gradient(circle 220px at calc(50% + 212px) calc(50% - 212px),rgba(40,110,185,.6) 99%,transparent 100%),radial-gradient(circle 220px at calc(50% + 300px) 50%,rgba(80,70,200,.55) 99%,transparent 100%),radial-gradient(circle 220px at calc(50% + 212px) calc(50% + 212px),rgba(98,26,150,.6) 99%,transparent 100%),radial-gradient(circle 220px at 50% calc(50% + 300px),rgba(150,40,160,.55) 99%,transparent 100%),radial-gradient(circle 220px at calc(50% - 212px) calc(50% + 212px),rgba(236,74,110,.55) 99%,transparent 100%),radial-gradient(circle 220px at calc(50% - 300px) 50%,rgba(255,92,52,.6) 99%,transparent 100%),radial-gradient(circle 220px at calc(50% - 212px) calc(50% - 212px),rgba(246,72,72,.6) 99%,transparent 100%)}
.strip{height:4px;background:linear-gradient(120deg,#f26a1b,#f2293f 22%,#e70c63 38%,#8705a1 62%,#4b129a 82%,#33449e)}
.card{max-width:420px;margin:6vh auto;background:#fff;border-radius:28px;padding:28px 32px;box-shadow:0 10px 40px rgba(59,13,107,.18);text-align:center}
form{text-align:left}h1{font-size:22px;margin:8px 0;color:#3b0d6b}label{display:grid;gap:4px;margin:12px 0;font-weight:600;font-size:14px}
input{font:inherit;padding:9px;border:1px solid rgba(26,20,38,.15);border-radius:10px;background:#fbf9fe}
button{font:inherit;font-weight:600;background:linear-gradient(120deg,#f26a1b,#f2293f 22%,#e70c63 38%,#8705a1 62%,#4b129a 82%,#33449e);color:#fff;border:0;border-radius:10px;padding:11px 16px;cursor:pointer;width:100%;box-shadow:0 4px 14px rgba(135,5,161,.28)}
.err{color:#d03b3b;font-weight:600}.sub{color:#4f4760;font-size:13px}img{width:72px;height:72px}</style></head>
<body><div class="strip"></div><div class="card"><img src="/logo" alt="NeuraNova logo">
<h1>Welcome to NeuraNova PA</h1><p class="sub">Create your login. Everything stays on this computer; you'll connect email, WhatsApp and AI next, inside the app.</p>
{error}<form method="post" action="/">
<label>Your email<input name="email" type="email" required value="{email}" autocomplete="username"></label>
<label>Your name<input name="name" required value="{name}"></label>
<label>Choose a password (at least 10 characters)<input name="password" type="password" required minlength="10" autocomplete="new-password"></label>
<label>Type it again<input name="password2" type="password" required minlength="10" autocomplete="new-password"></label>
<label>Timezone<input name="tz" required value="{tz}" data-known="{tz_known}"></label>
<button type="submit">Create login and start</button></form></div>
<script>(function(){var i=document.querySelector('[name=tz]');try{var z=Intl.DateTimeFormat().resolvedOptions().timeZone;
if(z&&i.dataset.known!=="1"){i.value=z;}}catch(e){}})();</script></body></html>"""

STARTING = """<!doctype html><html><head><meta charset="utf-8"><title>Starting NeuraNova PA</title></head>
<body style="font-family:'Segoe UI',system-ui;padding:40px;color:#3b0d6b"><h2>Starting NeuraNova PA…</h2>
<p>The sign-in screen opens by itself in a moment. Sign in with the email and password you just chose.</p>
<script>(function poll(){fetch('/health',{cache:'no-store'}).then(function(r){return r.json();}).then(function(d){
if(d&&d.version&&!d.setup){location.href='/login';}else{setTimeout(poll,800);}}).catch(function(){setTimeout(poll,800);});})();</script>
</body></html>"""


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
        guess = tz or guess_timezone()
        return HTMLResponse(FIRST_RUN.replace("{error}", f'<p class="err">{html.escape(error)}</p>' if error else "")
                            .replace("{email}", html.escape(email)).replace("{name}", html.escape(name))
                            .replace("{tz_known}", "1" if guess else "0")
                            .replace("{tz}", html.escape(guess or "Asia/Kolkata")))   # the page swaps in the PC's zone

    @app.get("/")
    def show():
        return form()

    @app.get("/health")
    def health():
        from . import __version__
        return {"ok": True, "app": "neuranova-pa", "version": __version__, "setup": True}

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
        open_later(f"http://localhost:{port}/", 0.5, wait_for="/")
    server.run()
    return done.is_set()


def windowed() -> bool:
    """True for the packaged Windows program without a console window."""
    return sys.stdout is None or sys.stderr is None


def send_output_to_log(home: Path) -> Path:
    """Without a console window, everything that would be printed goes to logs/neuranova-pa.log."""
    logs = home / "logs"
    logs.mkdir(exist_ok=True)
    path = logs / "neuranova-pa.log"
    if path.exists() and path.stat().st_size > 5_000_000:
        try:
            path.replace(logs / "neuranova-pa.old.log")
        except OSError:
            pass                      # another copy has it open; rotate next time
    stream = open(path, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = stream
    return path


def tell(message: str, wait: bool = False) -> None:
    """Print, and on the windowed Windows program also show it in a small message box."""
    print(message, flush=True)
    if sys.platform == "win32" and windowed_mode["on"]:
        import ctypes

        def box():
            ctypes.windll.user32.MessageBoxW(0, message.strip(), APP_NAME, 0x40 | 0x1000)
        if wait:
            box()
        else:
            threading.Thread(target=box, daemon=True).start()


windowed_mode = {"on": False}


def run_tray(home: Path, port: int, work) -> int:
    """Run `work` in the background and sit in the Windows system tray (next to the clock)."""
    import pystray
    from PIL import Image

    logo = Image.open(Path(__file__).parent / "static" / "neuranova-logo.png").convert("RGBA").resize((64, 64))
    result = {"code": 0}

    def background():
        try:
            result["code"] = work() or 0
        except SystemExit as exc:
            result["code"] = exc.code if isinstance(exc.code, int) else 1
            if exc.code not in (0, None):
                reason = exc.code if isinstance(exc.code, str) else (
                    f"it couldn't use the address http://localhost:{port} (another program may be blocking it). "
                    "Restart your computer and try again")
                tell(f"NeuraNova PA stopped: {reason}.\n\nDetails are in {home / 'logs' / 'neuranova-pa.log'}.", wait=True)
        except Exception as exc:
            result["code"] = 1
            tell(f"NeuraNova PA stopped because of an error:\n{exc}\n\nDetails are in {home / 'logs'}.", wait=True)
        finally:
            icon.stop()

    def open_app(icon_, item_=None):
        webbrowser.open(f"http://localhost:{port}/")

    def open_folder(icon_, item_):
        os.startfile(home)  # type: ignore[attr-defined]  # Windows only

    def quit_app(icon_, item_):
        icon_.stop()
        os._exit(0)

    icon = pystray.Icon("NeuraNova PA", logo, f"{APP_NAME} is running · http://localhost:{port}", menu=pystray.Menu(
        pystray.MenuItem("Open NeuraNova PA", open_app, default=True),
        pystray.MenuItem("Open my data folder", open_folder),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit NeuraNova PA", quit_app)))
    worker = threading.Thread(target=background, daemon=True)
    worker.start()
    try:
        icon.run()
    except Exception:
        print("System tray unavailable; NeuraNova PA keeps running without the tray icon.", flush=True)
        worker.join()
    os._exit(result["code"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="neuranova-pa", description=APP_NAME)
    parser.add_argument("--demo", action="store_true", help="open with sample data")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-tray", action="store_true", help="run in this window instead of the system tray")
    parser.add_argument("--port", type=int, default=int(os.environ.get("WEBHOOK_PORT") or PORT))
    args, rest = parser.parse_known_args(argv)
    home = home_dir()
    prepare(home)
    if windowed():
        windowed_mode["on"] = True
        send_output_to_log(home)
    print(f"{APP_NAME} · files in {home}", flush=True)

    from .cli import main as cli_main
    if rest:                                    # e.g. neuranova-pa report weekly
        if windowed_mode["on"] and rest[0] in ("setup", "auth", "cmd"):
            tell("That command needs a console. Use NeuraNova PA's Settings page in the browser instead.", wait=True)
            return 2
        return cli_main(rest)
    if port_busy(args.port):
        from . import __version__
        running = running_version(args.port)
        if running == __version__:
            print(f"{APP_NAME} is already running. Opening it in your browser.", flush=True)
            if not args.no_browser:
                webbrowser.open(f"http://localhost:{args.port}/")
            return 0
        free = next((p for p in range(args.port + 1, args.port + 30) if not port_busy(p)), None)
        what = "another copy of NeuraNova (an older version)" if running is not None else "another program"
        if free is None:
            tell(f"{what.capitalize()} is using http://localhost:{args.port} and no other address is free.\n"
                 "Close the other copy, then start NeuraNova PA again.", wait=True)
            return 1
        tell(f"Note: {what} is using http://localhost:{args.port}.\n"
             f"This version opens at http://localhost:{free} instead.\n"
             f"Close the other copy and restart NeuraNova PA to get back to :{args.port}.")
        args.port = free

    port = args.port

    def work() -> int:
        if args.demo:
            return cli_main(["demo", "--port", str(port)] + (["--no-browser"] if args.no_browser else []))
        if not configured(home):
            if not first_run(home, port, not args.no_browser):
                return 1
        elif not args.no_browser:
            open_later(f"http://localhost:{port}/")
        os.environ["WEBHOOK_PORT"] = str(port)
        os.environ["PUBLIC_URL"] = f"http://localhost:{port}"   # sign-in links follow the address in use today
        print(f"{APP_NAME} is running at http://localhost:{port}"
              + (" (in the system tray, next to the clock)." if windowed_mode["on"] else
                 " — keep this window open (Ctrl+C to stop)."), flush=True)
        return cli_main(["run"])

    if sys.platform == "win32" and not args.no_tray:
        try:
            import pystray  # noqa: F401
            from PIL import Image  # noqa: F401
        except Exception:
            pass
        else:
            return run_tray(home, port, work)
    return work()


if __name__ == "__main__":
    raise SystemExit(main())
