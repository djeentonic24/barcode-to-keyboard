#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Missing .venv. On Linux Mint: bash scripts/setup_host.sh"
  exit 1
fi
exec sudo "$ROOT/.venv/bin/python" "$ROOT/host/demo_gui.py" "$@"
