# Shared by the start scripts: create .venv the first time, then keep packages up to date.
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11 or newer is needed: https://www.python.org/downloads/" >&2
  exit 1
fi
if [ ! -d .venv ]; then
  echo "First run: setting up (about a minute)..."
  python3 -m venv .venv
  .venv/bin/python -m pip install --quiet --upgrade pip
fi
echo "Checking for updates to the agent's packages..."
.venv/bin/python -m pip install --quiet --disable-pip-version-check -e .
