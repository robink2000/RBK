#!/usr/bin/env bash
# NeuraNova console on this computer with sample data (Mac / Linux).
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_prepare.sh
exec .venv/bin/neuranova demo "$@"
