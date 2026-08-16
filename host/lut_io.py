"""Appendix A LUT helpers and CSV import/export (TZ slide 4–7)."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "host" / "presets"

CTRL_NAMES = {
    0x00: "NUL (ignore)",
    0x01: "SOH",
    0x02: "STX",
    0x03: "ETX",
    0x04: "EOT",
    0x05: "ENQ",
    0x06: "ACK",
    0x07: "BEL",
    0x08: "BS",
    0x09: "HT",
    0x0A: "LF Line Feed (element sep.)",
    0x0B: "VT",
    0x0C: "FF",
    0x0D: "CR Carriage Return (header term.)",
    0x0E: "SO",
    0x0F: "SI",
    0x10: "DLE",
    0x11: "DC1",
    0x12: "DC2",
    0x13: "DC3",
    0x14: "DC4",
    0x15: "NAK",
    0x16: "SYN",
    0x17: "ETB",
    0x18: "CAN",
    0x19: "EM",
    0x1A: "SUB",
    0x1B: "ESC",
    0x1C: "FS Field Separator",
    0x1D: "GS Group Separator",
    0x1E: "RS Record Separator",
    0x1F: "US Unit Separator",
    0x7F: "DEL (ignore)",
}


def default_lut() -> list[int]:
    lut = [0] * 256
    for c in range(0x20, 0x7F):
        lut[c] = c
    lut[0x0A] = 0x0A  # Enter via Keyboard.write('\\n')
    lut[0x0D] = 0x0A
    lut[0x1C] = 0x09
    lut[0x1D] = 0x09
    lut[0x1E] = 0x09
    lut[0x1F] = 0x09
    return lut


def preset_enter_delimiters() -> list[int]:
    lut = default_lut()
    for c in (0x1C, 0x1D, 0x1E, 0x1F):
        lut[c] = 0x0A
    return lut


def ascii_label(b: int) -> str:
    if 0x20 <= b <= 0x7E:
        return chr(b)
    return CTRL_NAMES.get(b, f"0x{b:02X}")


def action_label(mapped: int) -> str:
    if mapped == 0:
        return "Ignore"
    if mapped == 0x0A:
        return "KEY_ENTER"
    if mapped == 0x09:
        return "KEY_TAB"
    if 0x20 <= mapped <= 0x7E:
        return f"US QWERTY '{chr(mapped)}'"
    return f"0x{mapped:02X}"


def lut_to_csv_rows(lut: list[int]) -> list[dict[str, str]]:
    rows = []
    for i, mapped in enumerate(lut):
        rows.append(
            {
                "ascii_hex": f"0x{i:02X}",
                "name": ascii_label(i),
                "mapped_hex": f"0x{mapped:02X}",
                "hid_action": action_label(mapped),
            }
        )
    return rows


def write_csv(path: Path, lut: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ascii_hex", "name", "mapped_hex", "hid_action"])
        w.writeheader()
        w.writerows(lut_to_csv_rows(lut))


def read_csv(path: Path) -> list[int]:
    lut = [0] * 256
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            i = int(row["ascii_hex"], 16)
            lut[i] = int(row["mapped_hex"], 16) & 0xFF
    return lut


def ensure_presets() -> None:
    write_csv(PRESETS / "appendix_a_default.csv", default_lut())
    write_csv(PRESETS / "delimiters_as_enter.csv", preset_enter_delimiters())
