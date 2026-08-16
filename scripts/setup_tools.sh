#!/usr/bin/env bash
# Optional: arduino-cli + cores + st-flash (only if you need to re-flash boards).
set -euo pipefail
if [[ "${EUID}" -eq 0 ]]; then
  echo "Run as your user, not sudo ./setup_tools.sh"
  exit 1
fi
export PATH="$HOME/.local/bin:$PATH"
mkdir -p "$HOME/.local/bin"

install_arduino_cli() {
  if command -v arduino-cli >/dev/null 2>&1; then
    return
  fi
  echo "Installing arduino-cli to ~/.local/bin"
  curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh \
    | BINDIR="$HOME/.local/bin" sh
}

if command -v pacman >/dev/null 2>&1; then
  sudo pacman -Sy --needed --noconfirm arduino-cli python-pyserial tk stlink openocd curl
elif command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3-serial python3-tk stlink-tools openocd curl
  install_arduino_cli
else
  echo "Need pacman or apt-get"
  exit 1
fi

install_arduino_cli

arduino-cli config init --overwrite >/dev/null
arduino-cli config add board_manager.additional_urls \
  https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli config add board_manager.additional_urls \
  https://github.com/stm32duino/BoardManagerFiles/raw/main/package_stmicroelectronics_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32
arduino-cli core install STMicroelectronics:stm32
echo "OK. Flash: bash scripts/flash_esp.sh /dev/ttyUSB0 && bash scripts/flash_stm.sh"
echo "If arduino-cli is missing after this, add ~/.local/bin to PATH."
