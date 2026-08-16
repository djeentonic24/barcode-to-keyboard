# UART → USB HID Keyboard Bridge (demo)

Customer demo of the RFP in `Pjt HID-UART.pptx`: a PDF417/AAMVA scanner speaks UART; an STM32 translates bytes with a 256-entry LUT and types **US QWERTY USB HID** into the host (gedit, LibreOffice, or this Linux GUI).

This tree is the **Linux + ESP32 scanner + STM32F4VE** stand. Production target remains NUCLEO-C071RB + Windows configurator.

## Run on Linux Mint (demo PC)

Boards are already programmed. The Mint machine only needs Python + Tk. Plug:

- STM32 **Mini-USB** → PC (enumerates as HID keyboard `BarcodeHID`)
- ESP32 **USB-C** → PC (power + Scan trigger)
- ST-Link is **not** required to run the demo
- F4VE J6 USB-UART is optional (config only)

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip python3-tk
git clone https://github.com/djeentonic24/barcode-to-keyboard.git
cd barcode-to-keyboard
bash scripts/setup_host.sh
bash scripts/run_gui.sh
```

In the GUI pick the **ESP** serial port (CH340). Two `/dev/ttyUSB*` can swap; it is not the STM J6 adapter. **Scan** or the ESP **BOOT** button. The window shows what the STM actually typed as HID (`sudo` is used so `/dev/input` can be grabbed).

Without Tk: `sudo .venv/bin/python host/demo_gui.py --cli`

If serial access is denied without sudo, log out and back in after `setup_host.sh` (groups `dialout`, `input`).

## Hardware

### Scanner UART

| ESP32 | STM32 F4VE |
|-------|------------|
| D17 (GPIO17) | PA3 |
| GND | GND |

Power the F4VE from Mini-USB only (do not also feed 5V pins).

### ST7789 (M130T-240240-RGB-7) on the ESP32 — 3.3 V only

Silk **SCL/SDA is SPI**, not I2C. No CS pin (tied to GND on the module).

| Module | ESP32 |
|--------|-------|
| GND | GND |
| VCC | 3V3 |
| SCL | D18 |
| SDA | D23 (MOSI) |
| RES | D22 |
| DC | D21 |
| BLK | D32 (or 3V3) |

## Re-flash firmware (optional)

Needs `arduino-cli`, cores `esp32:esp32` and `STMicroelectronics:stm32`, plus `st-flash`. The STM core download is large (~270 MB).

```bash
bash scripts/setup_tools.sh
bash scripts/flash_esp.sh /dev/ttyUSB0    # ESP CH340; try ttyUSB1 if upload fails
bash scripts/flash_stm.sh                 # ST-Link on F4VE SWD, BOOT0=0
```

Regenerate the PDF417 bitmap after changing `host/payload.py`:

```bash
.venv/bin/python scripts/gen_assets.py
```

LUT (Appendix A): `0x20–0x7E` as-is; `LF`/`CR` → Enter; `FS/GS/RS/US` → Tab (or Enter via `host/presets/delimiters_as_enter.csv`); other controls dropped.

Config protocol (Mode 2, J6 USART1): [`docs/config_protocol.md`](docs/config_protocol.md).

## Layout

| Path | Role |
|------|------|
| `firmware/esp_scanner` | Fake scanner + ST7789 PDF417 |
| `firmware/stm32_hid_bridge` | UART ring + HID + config protocol |
| `host/` | Payload, LUT CSV, GUI, HID capture |
| `docs/config_protocol.md` | 64-byte config frames |
| `scripts/setup_host.sh` | Mint/Ubuntu: venv + Tk |
| `scripts/run_gui.sh` | `sudo` GUI |
| `DEVBOARD_F4VE.md` | Board pinout |
| `Pjt HID-UART.pptx` | RFP |

## Out of scope here

NUCLEO-C071RB, Windows `.exe`, native HID Feature Reports — same protocol, different transport, after this demo.
