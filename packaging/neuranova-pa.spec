# PyInstaller build of NeuraNova PA (one folder: NeuraNova PA\NeuraNova PA.exe + _internal\).
#   pyinstaller packaging/neuranova-pa.spec --noconfirm
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = SPECPATH + "/.."
datas = [(ROOT + "/neuranova.toml", "."), (ROOT + "/.env.example", ".")]
binaries, hidden = [], []
for pkg in ("neuranova", "uvicorn", "tzdata", "apscheduler", "anthropic", "openai", "icalendar",
            "recurring_ical_events", "x_wr_timezone", "certifi", "googleapiclient", "google_auth_oauthlib",
            "msal", "multipart", "python_multipart", "playwright", "pystray"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hidden += h
# Google's discovery documents are ~100 MB; only Gmail's is used.
datas = [(src, dst) for src, dst in datas
         if "discovery_cache" not in src.replace("\\", "/") or "gmail.v1" in src or not src.endswith(".json")]
hidden += collect_submodules("fastapi") + collect_submodules("starlette")

a = Analysis([SPECPATH + "/neuranova_pa.py"], pathex=[ROOT + "/src"], binaries=binaries, datas=datas,
             hiddenimports=hidden, excludes=["tkinter", "pytest", "IPython", "matplotlib", "numpy"], noarchive=False)
a.datas = [d for d in a.datas if "discovery_cache" not in d[0].replace("\\", "/") or "gmail.v1" in d[0]]
pyz = PYZ(a.pure)
# UTF-8 mode: files and .env are always read/written as UTF-8, whatever the Windows language
utf8 = [("X utf8_mode=1", None, "OPTION")]
exe = EXE(pyz, a.scripts, utf8, exclude_binaries=True, name="NeuraNova PA", console=False,
          icon=SPECPATH + "/neuranova.ico" if __import__("os").path.exists(SPECPATH + "/neuranova.ico") else None)
coll = COLLECT(exe, a.binaries, a.datas, name="NeuraNova PA")
