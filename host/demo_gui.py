#!/usr/bin/env python3
"""Linux demo GUI: trigger ESP scan, capture STM HID, compare to Appendix A LUT."""
from __future__ import annotations

import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.hiddecode import find_hid, HidGrab  # noqa: E402
from host.payload import AAMVA_FIELDS, EXPECTED_HID, SAMPLE  # noqa: E402

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

BG = "#12141a"
PANEL = "#1c2028"
FG = "#e8eaed"
MUTED = "#8b93a1"
ACCENT = "#5b8def"
OK = "#3dd68c"
BAD = "#ff6b6b"
MONO = ("DejaVu Sans Mono", 10)
SANS = ("DejaVu Sans", 11)
TITLE = ("DejaVu Sans", 16, "bold")


def serial_ports() -> list[str]:
    if list_ports is None:
        return []
    return [p.device for p in list_ports.comports()]


def trigger_esp(port: str) -> str:
    if serial is None:
        raise RuntimeError("pyserial is not installed")
    ser = serial.Serial(port, 115200, timeout=1)
    try:
        time.sleep(0.15)
        ser.reset_input_buffer()
        ser.write(b"s")
        ser.flush()
        time.sleep(0.4)
        return ser.read(512).decode("utf-8", "replace")
    finally:
        ser.close()


class DemoApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("UART → USB HID Keyboard  ·  demo")
        self.configure(bg=BG)
        self.geometry("980x720")
        self.minsize(840, 600)
        self._busy = False
        self._build()
        self.refresh_devices()

    def _build(self) -> None:
        pad = {"padx": 18, "pady": 8}
        tk.Label(
            self,
            text="STM32 UART → USB HID keyboard",
            font=TITLE,
            bg=BG,
            fg=FG,
        ).pack(anchor="w", **pad)
        tk.Label(
            self,
            text="Scanner (ESP32) sends AAMVA UART  ·  bridge types US QWERTY HID  ·  Linux host",
            font=SANS,
            bg=BG,
            fg=MUTED,
        ).pack(anchor="w", padx=18)

        status = tk.Frame(self, bg=PANEL)
        status.pack(fill="x", padx=18, pady=12)
        self.hid_var = tk.StringVar(value="HID: searching…")
        self.esp_var = tk.StringVar(value="ESP: —")
        tk.Label(status, textvariable=self.hid_var, font=SANS, bg=PANEL, fg=FG).pack(
            anchor="w", padx=12, pady=(10, 2)
        )
        row = tk.Frame(status, bg=PANEL)
        row.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(row, textvariable=self.esp_var, font=SANS, bg=PANEL, fg=FG).pack(
            side="left"
        )
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(row, textvariable=self.port_var, width=18, state="readonly")
        self.port_box.pack(side="right", padx=(8, 0))
        tk.Label(row, text="ESP serial", font=SANS, bg=PANEL, fg=MUTED).pack(side="right")

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", padx=18)
        self.scan_btn = tk.Button(
            btns,
            text="  Scan  ",
            font=("DejaVu Sans", 12, "bold"),
            bg=ACCENT,
            fg="white",
            activebackground="#4a7ad4",
            relief="flat",
            command=self.on_scan,
        )
        self.scan_btn.pack(side="left")
        tk.Button(
            btns,
            text="Refresh devices",
            font=SANS,
            bg=PANEL,
            fg=FG,
            relief="flat",
            command=self.refresh_devices,
        ).pack(side="left", padx=10)
        self.match_var = tk.StringVar(value="")
        tk.Label(btns, textvariable=self.match_var, font=SANS, bg=BG, fg=MUTED).pack(
            side="left", padx=12
        )

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=8)

        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="HID received (from STM)", font=SANS, bg=BG, fg=MUTED).pack(
            anchor="w"
        )
        self.got = tk.Text(
            left, font=MONO, bg=PANEL, fg=FG, insertbackground=FG, wrap="word", height=16
        )
        self.got.pack(fill="both", expand=True, pady=(4, 0))

        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        tk.Label(right, text="Expected after LUT (Appendix A)", font=SANS, bg=BG, fg=MUTED).pack(
            anchor="w"
        )
        self.exp = tk.Text(
            right, font=MONO, bg=PANEL, fg=MUTED, wrap="word", height=16
        )
        self.exp.pack(fill="both", expand=True, pady=(4, 0))
        preview = EXPECTED_HID.replace("\t", "⇥").replace("\n", "↵\n")
        self.exp.insert("1.0", preview)
        self.exp.configure(state="disabled")

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill="x", padx=18, pady=(0, 14))
        fields = (
            f"Parsed AAMVA:  {AAMVA_FIELDS['DAC']} {AAMVA_FIELDS['DCS']}   "
            f"DL {AAMVA_FIELDS['DAQ']}   {AAMVA_FIELDS['DAG']}, "
            f"{AAMVA_FIELDS['DAI']} {AAMVA_FIELDS['DAJ']}   "
            f"payload {len(SAMPLE)} bytes"
        )
        tk.Label(foot, text=fields, font=SANS, bg=BG, fg=MUTED).pack(anchor="w")
        tk.Label(
            foot,
            text="HID grab keeps keystrokes in this window. Need access to /dev/input (sudo or group input).",
            font=("DejaVu Sans", 9),
            bg=BG,
            fg=MUTED,
        ).pack(anchor="w", pady=(4, 0))

    def refresh_devices(self) -> None:
        path, name, vid, pid = find_hid()
        if path:
            self.hid_var.set(f"HID: {name}  {vid:04X}:{pid:04X}  {path}")
        else:
            self.hid_var.set("HID: not found — plug STM Mini-USB (BarcodeHID)")
        ports = serial_ports()
        self.port_box["values"] = ports
        if ports and not self.port_var.get():
            # Prefer CH340 that is usually ESP (higher ttyUSB number is a heuristic).
            self.port_var.set(ports[-1])
        self.esp_var.set("ESP: select serial port, then Scan")

    def on_scan(self) -> None:
        if self._busy:
            return
        port = self.port_var.get()
        path, _, _, _ = find_hid()
        if not port:
            self.match_var.set("Select ESP serial port")
            return
        if not path:
            self.match_var.set("STM HID not found")
            return
        self._busy = True
        self.scan_btn.configure(state="disabled")
        self.match_var.set("Scanning…")
        self.got.delete("1.0", "end")
        threading.Thread(target=self._scan_worker, args=(port, path), daemon=True).start()

    def _scan_worker(self, port: str, hid_path: str) -> None:
        err = ""
        received = ""
        esp_log = ""
        try:
            with HidGrab(hid_path, grab=True) as hid:
                esp_log = trigger_esp(port)
                received = hid.collect(seconds=4.0, idle=0.4)
        except PermissionError:
            err = "No permission for HID (/dev/input). Run: sudo python -m host.demo_gui"
        except Exception as exc:
            err = str(exc)

        def done() -> None:
            self._busy = False
            self.scan_btn.configure(state="normal")
            if err:
                self.match_var.set(err)
                return
            shown = received.replace("\t", "⇥").replace("\n", "↵\n")
            self.got.insert("1.0", shown)
            if received == EXPECTED_HID:
                self.match_var.set("MATCH  LUT output is identical to spec")
            else:
                self.match_var.set(
                    f"MISMATCH  got {len(received)} chars, expected {len(EXPECTED_HID)}"
                )
            if esp_log.strip():
                self.esp_var.set("ESP: " + esp_log.strip().splitlines()[-1])

        self.after(0, done)


def main() -> None:
    DemoApp().mainloop()


if __name__ == "__main__":
    main()
