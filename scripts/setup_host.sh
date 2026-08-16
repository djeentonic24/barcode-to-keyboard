#!/usr/bin/env bash
# Host PC (Linux Mint / Ubuntu): venv + Tk + serial. Firmware stays on the boards.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run as your user: bash scripts/setup_host.sh"
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This script is for Debian/Ubuntu/Linux Mint (apt)."
  echo "On Arch: sudo pacman -S python python-pip tk && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip python3-tk

python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install -U pip
"$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
"$ROOT/.venv/bin/python" "$ROOT/host/test_payload.py"

sudo usermod -aG dialout,plugdev,input "$USER" || true

echo
echo "OK. GUI:"
echo "  sudo $ROOT/.venv/bin/python $ROOT/host/demo_gui.py"
echo "  or:  bash scripts/run_gui.sh"
echo
echo "If serial/HID is denied without sudo, log out and back in (groups: dialout,input)."
echo "Plug STM Mini-USB (HID) and ESP USB-C. Pick the ESP serial port, then Scan or ESP BOOT."
