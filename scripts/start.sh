#!/usr/bin/env bash
# Your real NeuraNova console (Mac / Linux). The first time, it asks a few setup questions.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_prepare.sh
if ! grep -qs '^DASHBOARD_PASSWORD=.\+' .env; then
  .venv/bin/neuranova setup
else
  exec .venv/bin/neuranova run "$@"
fi
