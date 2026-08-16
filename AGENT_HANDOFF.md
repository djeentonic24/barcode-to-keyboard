# Handoff for next agent

## Goal (client RFP)

Build a **STM32 UART → USB HID keyboard bridge** on **NUCLEO-C071RB** plus a **Windows configurator**.

- Scanner sends raw UART ASCII (bursts up to ~1–3 KB, AAMVA control bytes: CR/LF/FS/GS/RS/US).
- STM32 maps bytes via a 256-entry LUT to US QWERTY HID keystrokes (Notepad/Excel).
- Config without reflash: baud/parity/stop, inter-character delay 0–20 ms, LUT — all in internal Flash.
- Windows app: detect device, read/write settings, CSV import/export for LUT, Restore defaults / Save.
- Spec also mentions flashing `.bin` from GUI — treat as optional unless client confirms; prefer ST DFU/CubeProgrammer path first.
- Modes: keyboard vs config, **not simultaneous**.
- Deliverables: source, setup/build/flash guide, protocol spec, 30-day minor-bug warranty after acceptance.

Authoritative brief: `Pjt HID-UART.pptx`.

## What already exists (MVP demo)

Path: `mvp/`

| Piece | Role |
|---|---|
| `esp_scanner_sim/esp_scanner_sim.ino` | Fake scanner: AAMVA-like burst on ESP32 UART (GPIO17 TX) |
| `pc_scanner_sim.py` | Same burst over USB-UART COM port (`pyserial`) |
| `stm32_hid_bridge/stm32_hid_bridge.ino` | STM32F4VE Arduino sketch: USART2 RX → ring buffer → LUT → USB HID keyboard |

**Hypothesis proven locally:** UART burst → HID typing. Demo hardware is **STM32F4VE**, not C071. Host demo was/planned on **Linux**; product target is **Windows**.

Wiring reminder (F4VE):
- Scanner TX → STM32 **PA3** (USART2 RX), common GND.
- STM32 Mini-USB → PC as HID keyboard.
- Power F4VE from USB only (do not dual-power 5V).

Arduino_Core_STM32: Black F407VE, USB = HID Keyboard, CDC off.

## Agreed commercial milestones (1 month)

1. **Free demo** — already: ESP/PC → STM → HID (show on call).
2. **Target HW + Windows CLI (40%)** — firmware on NUCLEO-C071RB + CLI for detect / read-write UART+LUT / CSV / save Flash.
3. **Windows GUI (40%)** — same features as CLI in a standalone `.exe`.
4. **Docs (20%)** — setup/build/flash, protocol spec, commented sources; warranty starts at acceptance.

## Next agent tasks (priority order)

### 1. Port firmware to NUCLEO-C071RB (Cube HAL)

- UART RX DMA + ring buffer **≥ 3 KB**.
- Default LUT per Appendix A in the PPTX:
  - `0x20–0x7E` → US QWERTY (+Shift as needed)
  - `0x0A`/`0x0D` → Enter
  - `0x1C–0x1F` → Enter or Tab
  - other controls → ignore (`0x00`)
- Configurable inter-character delay 0–20 ms.
- USB Device: HID keyboard + config channel (prefer **HID Feature Reports** or vendor HID; avoid CDC unless needed).
- Flash settings block: magic, version, CRC, UART params, delay, LUT; invalid CRC → factory defaults.
- Keyboard reports must not leak config traffic.

### 2. Define and implement USB config protocol

Commands roughly: ping, get/set UART, get/set LUT (chunked), restore defaults, commit Flash, return to keyboard mode. Document packet format.

### 3. Windows CLI utility

- Auto-detect by VID/PID.
- Read / write UART settings and LUT; CSV import/export; Restore defaults; Save to device.
- Stack suggestion: C# + HidSharp (or similar), single tool that later shares logic with GUI.

### 4. Windows GUI

- Same features as CLI; file/preset-first UX for LUT (CSV), not only cell-by-cell editing.
- Read / Restore defaults / Save to device.

### 5. Documentation

- Toolchain, flash procedure, pinout, how to test with ESP or `pc_scanner_sim.py`.
- Protocol specification.
- Brief debug tips.

### 6. Out of scope unless confirmed

- Custom IAP / in-app `.bin` flash (add days if required).
- Non-US layouts, macOS/Linux product GUI, enclosure, real scanner hardware.

## Risks / notes

- C071 USB Device stack is the hard part; F4 MVP does not prove C0 USB.
- HID typing is much slower than UART; buffer must absorb full barcode then drain with delay.
- Client board: NUCLEO-C071RB — obtain/access before promising flash demos on target silicon.
- Repo remote: `https://github.com/djeentonic24/barcode-to-keyboard` (HTTPS; SSH key may be missing on this machine).

## Suggested first actions

1. Read `Pjt HID-UART.pptx` (or extract slide text) and lock buffer size / config channel / `.bin` flash scope with user if unclear.
2. Create CubeIDE (or PlatformIO) project for STM32C071RB USB HID + UART DMA.
3. Reuse LUT defaults and test payloads from `mvp/`.
4. Add Windows CLI against Feature Reports as soon as firmware answers `ping`.
