#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"
FQBN_ESP="${FQBN_ESP:-esp32:esp32:esp32}"
PORT="${1:-/dev/ttyUSB1}"
arduino-cli compile --fqbn "$FQBN_ESP" "$ROOT/firmware/esp_scanner"
arduino-cli upload -p "$PORT" --fqbn "$FQBN_ESP" "$ROOT/firmware/esp_scanner"
echo "ESP flashed on $PORT"
