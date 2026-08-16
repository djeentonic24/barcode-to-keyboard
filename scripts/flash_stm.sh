#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"
FQBN='STMicroelectronics:stm32:GenF4:pnum=BLACK_F407VE,usb=HID,upload_method=OpenOCDSTLink'
arduino-cli compile --fqbn "$FQBN" "$ROOT/firmware/stm32_hid_bridge"
BIN="$(find "$HOME/.cache/arduino/sketches" -name 'stm32_hid_bridge.ino.bin' -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
if [[ -z "$BIN" || ! -f "$BIN" ]]; then
  echo "compiled .bin not found"
  exit 1
fi
st-flash --reset write "$BIN" 0x08000000
echo "STM32 flashed ($BIN)"
