#!/usr/bin/env bash
# Toolchain for the F4VE + ESP32 demo. Run as your user (sudo only for pacman).
set -euo pipefail
if [[ "${EUID}" -eq 0 ]]; then
  echo "Run as your user, not sudo ./setup_tools.sh"
  exit 1
fi
sudo pacman -Sy --needed --noconfirm arduino-cli python-pyserial python-tkinter stlink openocd || \
  sudo apt-get install -y arduino-cli python3-serial python3-tk stlink-tools openocd || true
arduino-cli config init --overwrite >/dev/null
arduino-cli config add board_manager.additional_urls \
  https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli config add board_manager.additional_urls \
  https://github.com/stm32duino/BoardManagerFiles/raw/main/package_stmicroelectronics_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32
arduino-cli core install STMicroelectronics:stm32
echo "OK. Next: pip install -r requirements.txt && bash scripts/flash_esp.sh && bash scripts/flash_stm.sh"
