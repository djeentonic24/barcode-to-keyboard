# UART → USB HID Keyboard Bridge (demo)

Customer demo of the RFP in `Pjt HID-UART.pptx`: a PDF417/AAMVA scanner speaks UART; an STM32 translates bytes with a 256-entry LUT and types **US QWERTY USB HID** into the host (Notepad, gedit, or the Linux GUI).

This tree is the **Linux + ESP32 scanner + STM32F4VE** stand. Production target in the RFP remains NUCLEO-C071RB + Windows configurator.

## Data path

```
ESP32  GPIO17 TX  ──UART 115200 8N1──►  STM32 PA3 (USART2 RX)
ESP32  ST7789        shows the real PDF417 of the same payload
STM32  Mini-USB  ──HID keyboard──►  Linux (BarcodeHID)
```

ESP USB-C is power + trigger only. The USB-UART dongle on F4VE J6 is debug, not part of the spec.

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

Disconnect this panel from the STM if it was wired there.

Trigger a scan with the ESP **BOOT** button, `python host/trigger_scan.py /dev/ttyUSB1`, or the GUI **Scan** button.

## Host software (Linux)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# optional: sudo usermod -aG uucp,input $USER && re-login
.venv/bin/python host/payload.py          # LUT / AAMVA self-check
.venv/bin/python host/demo_gui.py         # demo UI (sudo if HID grab denied)
```

The GUI grabs the STM HID device so keystrokes stay in the window, sends `s` to the ESP, and checks the result against Appendix A.

## Firmware

Needs `arduino-cli`, cores `esp32:esp32` and `STMicroelectronics:stm32`, plus `st-flash` for the F4VE.

```bash
bash scripts/setup_tools.sh               # once, on Arch/CachyOS or apt fallback
bash scripts/flash_esp.sh /dev/ttyUSB1
bash scripts/flash_stm.sh
```

Regenerate the PDF417 bitmap after changing `host/payload.py`:

```bash
.venv/bin/pip install pdf417gen
.venv/bin/python scripts/gen_assets.py
```

LUT (Appendix A): `0x20–0x7E` as-is; `LF`/`CR` → Enter; `FS/GS/RS/US` → Tab; other controls dropped.

## Layout

| Path | Role |
|------|------|
| `firmware/esp_scanner` | Fake scanner + ST7789 PDF417 |
| `firmware/stm32_hid_bridge` | UART DMA-less ring + HID |
| `host/` | Payload, LUT, GUI, HID capture |
| `scripts/` | Asset gen + flash |
| `DEVBOARD_F4VE.md` | Board pinout |
| `Pjt HID-UART.pptx` | RFP |

## Out of scope here

Windows GUI, NUCLEO-C071RB, in-app `.bin` flash, Feature Report config — next milestone after this demo.
