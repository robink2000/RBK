#!/usr/bin/env bash
# NeuraNova console on this computer with sample data (Mac / Linux).
# First run installs everything into .venv; later runs start in a few seconds.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11 or newer is needed: https://www.python.org/downloads/" >&2
  exit 1
fi
if [ ! -d .venv ]; then
  echo "First run: setting up (about a minute)..."
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -e .
fi
exec .venv/bin/neuranova demo "$@"
