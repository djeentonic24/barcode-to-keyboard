#!/usr/bin/env python3
"""Linux demo GUI: Mode 1 HID bridge + Mode 2 configurator."""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.device_link import Device, probe_port  # noqa: E402
from host.hiddecode import HidGrab, find_hid  # noqa: E402
from host.lut_io import (  # noqa: E402
    PRESETS,
    action_label,
    ascii_label,
    default_lut,
    ensure_presets,
    preset_enter_delimiters,
    read_csv,
    write_csv,
)

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

TK_HINT = """Tk is missing (libtk8.6.so):

  Linux Mint / Ubuntu:  sudo apt install python3-tk
  Arch / CachyOS:       sudo pacman -S tk

Then:  bash scripts/run_gui.sh
CLI:   sudo .venv/bin/python host/demo_gui.py --cli
"""


def serial_ports() -> list[str]:
    if list_ports is None:
        return []
    return [p.device for p in list_ports.comports()]


def open_tty(port: str, baud: int = 115200, timeout: float = 0.2):
    if serial is None:
        raise RuntimeError("pyserial is not installed")
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = timeout
    ser.dsrdtr = False
    ser.rtscts = False
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser


def wait_esp_ready(ser, seconds: float = 2.0) -> str:
    """CH340 often resets ESP on first open; wait for the scanner banner."""
    deadline = time.time() + seconds
    buf = bytearray()
    while time.time() < deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf.extend(chunk)
            low = bytes(buf).lower()
            if b"ready" in low or b"scanner" in low or b"gpio17" in low:
                break
        else:
            time.sleep(0.02)
    return bytes(buf).decode("utf-8", "replace")


def show_hid(text: str) -> str:
    return text.replace("\t", "⇥").replace("\n", "↵\n")


def run_cli(port: str | None) -> int:
    path, name, vid, pid = find_hid()
    ports = serial_ports()
    print("Mode 1 bridge test (CLI)")
    if not path:
        print("HID: not found")
        return 1
    print(f"HID: {name} {vid:04X}:{pid:04X}")
    port = port or (ports[-1] if ports else "")
    if not port:
        print("no serial ports")
        return 1
    print(f"ESP: {port}  Enter to scan")
    try:
        input()
    except EOFError:
        return 1
    try:
        ser = open_tty(port)
        wait_esp_ready(ser)
        with HidGrab(path, grab=True) as hid:
            ser.write(b"s")
            ser.flush()
            received = hid.collect(8.0, 0.6)
        ser.close()
    except PermissionError:
        print("need sudo / group input")
        return 1
    print(show_hid(received))
    print(f"{len(received)} HID characters")
    return 0 if received else 2


def run_gui() -> None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:
        raise SystemExit(TK_HINT) from exc

    ensure_presets()

    class App(tk.Tk):
        def __init__(self) -> None:
            super().__init__()
            self.title("UART-to-USB HID Keyboard")
            self.geometry("1100x740")
            self.minsize(960, 620)
            self.lut = default_lut()
            self.dev: Device | None = None
            self.cfg_ser = None
            self.esp_ser = None
            self.cfg_port = tk.StringVar()
            self.esp_port = tk.StringVar()
            self.hid_status = tk.StringVar(value="HID: searching…")
            self.dev_status = tk.StringVar(value="Config: not connected")
            self.status = tk.StringVar(value="Mode 1: BOOT on ESP or Scan. Keystrokes stay in this window.")
            self.baud = tk.StringVar(value="115200")
            self.parity = tk.StringVar(value="None")
            self.stop = tk.StringVar(value="1")
            self.delay = tk.DoubleVar(value=5.0)
            self.preset = tk.StringVar(value="appendix_a_default.csv")
            self.bin_path = tk.StringVar()
            self.filter_mod = tk.BooleanVar(value=True)
            self.hid_grab = None
            self._hid_after = None
            self._hid_raw: list[str] = []
            self._esp_ready = False
            self._style()
            self._build()
            self.refresh_ports(probe=False)
            self.start_hid_listen()
            self.protocol("WM_DELETE_WINDOW", self.on_close)

        def _style(self) -> None:
            st = ttk.Style(self)
            if "clam" in st.theme_names():
                st.theme_use("clam")
            st.configure("Title.TLabel", font=("DejaVu Sans", 16, "bold"))
            st.configure("Muted.TLabel", foreground="#444444")
            st.configure("Accent.TButton", padding=(10, 4))

        def _build(self) -> None:
            top = ttk.Frame(self, padding=(12, 10, 12, 4))
            top.pack(fill="x")
            ttk.Label(top, text="STM32 UART → USB HID Keyboard Bridge", style="Title.TLabel").pack(anchor="w")
            ttk.Label(
                top,
                text="Scanner UART → LUT → US QWERTY HID. This window only shows what the STM actually typed.",
                style="Muted.TLabel",
            ).pack(anchor="w")

            bar = ttk.LabelFrame(self, text="Devices", padding=8)
            bar.pack(fill="x", padx=12, pady=6)
            ttk.Label(bar, textvariable=self.hid_status).grid(row=0, column=0, columnspan=8, sticky="w")
            ttk.Label(bar, textvariable=self.dev_status).grid(row=1, column=0, columnspan=8, sticky="w", pady=(2, 8))

            ttk.Label(bar, text="ESP (scanner)").grid(row=2, column=0, sticky="w")
            self.esp_combo = ttk.Combobox(bar, textvariable=self.esp_port, width=16, state="readonly")
            self.esp_combo.grid(row=2, column=1, padx=6)
            self.esp_combo.bind("<<ComboboxSelected>>", lambda _e: self.close_esp())
            ttk.Button(bar, text="Scan", command=self.bridge_scan, style="Accent.TButton").grid(row=2, column=2, padx=3)
            ttk.Button(bar, text="Clear", command=self.clear_hid).grid(row=2, column=3, padx=3)
            ttk.Button(bar, text="Refresh", command=self.on_refresh).grid(row=2, column=4, padx=3)

            ttk.Label(bar, text="STM config (J6)").grid(row=3, column=0, sticky="w", pady=(8, 0))
            self.cfg_combo = ttk.Combobox(bar, textvariable=self.cfg_port, width=16, state="readonly")
            self.cfg_combo.grid(row=3, column=1, padx=6, pady=(8, 0))
            ttk.Button(bar, text="Connect", command=self.connect).grid(row=3, column=2, padx=3, pady=(8, 0))
            ttk.Button(bar, text="Disconnect", command=self.disconnect).grid(row=3, column=3, padx=3, pady=(8, 0))

            self.nb = ttk.Notebook(self)
            self.nb.pack(fill="both", expand=True, padx=12, pady=(0, 6))
            self.tab_test = ttk.Frame(self.nb, padding=8)
            self.tab_cfg = ttk.Frame(self.nb, padding=8)
            self.nb.add(self.tab_test, text="Mode 1  Bridge test")
            self.nb.add(self.tab_cfg, text="Mode 2  Configuration")
            self._build_test()
            self._build_cfg()
            self.nb.bind("<<NotebookTabChanged>>", self.on_tab)

            ttk.Label(self, textvariable=self.status, padding=(12, 4)).pack(fill="x", side="bottom")

        def _build_test(self) -> None:
            ttk.Label(
                self.tab_test,
                text="ESP BOOT or Scan → STM types HID. Capture is live from BarcodeHID, not a stored payload.",
                style="Muted.TLabel",
            ).pack(anchor="w")
            ttk.Label(self.tab_test, text="HID received").pack(anchor="w", pady=(8, 0))
            self.got = tk.Text(self.tab_test, height=22, font=("DejaVu Sans Mono", 10), wrap="word")
            self.got.pack(fill="both", expand=True, pady=(4, 8))
            self.match = ttk.Label(self.tab_test, text="BOOT on ESP or Scan.", font=("DejaVu Sans", 11, "bold"))
            self.match.pack(anchor="w")

        def _build_cfg(self) -> None:
            uart = ttk.LabelFrame(self.tab_cfg, text="UART settings (scanner USART2)", padding=8)
            uart.pack(fill="x")
            ttk.Label(uart, text="Baud").grid(row=0, column=0, sticky="w")
            ttk.Combobox(
                uart,
                textvariable=self.baud,
                values=("9600", "19200", "38400", "57600", "115200"),
                width=10,
                state="readonly",
            ).grid(row=0, column=1, padx=6)
            ttk.Label(uart, text="Parity").grid(row=0, column=2, sticky="w")
            ttk.Combobox(
                uart, textvariable=self.parity, values=("None", "Even", "Odd"), width=8, state="readonly"
            ).grid(row=0, column=3, padx=6)
            ttk.Label(uart, text="Stop bits").grid(row=0, column=4, sticky="w")
            ttk.Combobox(uart, textvariable=self.stop, values=("1", "2"), width=4, state="readonly").grid(
                row=0, column=5, padx=6
            )
            ttk.Label(uart, text="Inter-character delay (ms)").grid(row=1, column=0, sticky="w", pady=(10, 0))
            ttk.Scale(
                uart,
                from_=0,
                to=20,
                variable=self.delay,
                orient="horizontal",
                length=240,
                command=self._on_delay,
            ).grid(row=1, column=1, columnspan=3, sticky="we", pady=(10, 0))
            self.delay_lbl = ttk.Label(uart, text="5 ms")
            self.delay_lbl.grid(row=1, column=4, sticky="w", pady=(10, 0))

            lutf = ttk.LabelFrame(self.tab_cfg, text="Lookup table  ·  CSV / presets, Appendix A", padding=8)
            lutf.pack(fill="both", expand=True, pady=8)
            prow = ttk.Frame(lutf)
            prow.pack(fill="x")
            ttk.Label(prow, text="Preset").pack(side="left")
            self.preset_box = ttk.Combobox(prow, textvariable=self.preset, width=28, state="readonly")
            self.preset_box.pack(side="left", padx=6)
            ttk.Button(prow, text="Load preset", command=self.load_preset).pack(side="left", padx=3)
            ttk.Button(prow, text="Import CSV…", command=self.import_csv).pack(side="left", padx=3)
            ttk.Button(prow, text="Export CSV…", command=self.export_csv).pack(side="left", padx=3)
            ttk.Checkbutton(
                prow, text="Show non-default only", variable=self.filter_mod, command=self.fill_lut
            ).pack(side="left", padx=12)

            cols = ("hex", "name", "mapped", "action")
            self.tree = ttk.Treeview(lutf, columns=cols, show="headings", height=12)
            for c, t, w in (
                ("hex", "ASCII", 70),
                ("name", "Name / glyph", 300),
                ("mapped", "Mapped", 80),
                ("action", "USB HID target", 240),
            ):
                self.tree.heading(c, text=t)
                self.tree.column(c, width=w, stretch=True)
            sy = ttk.Scrollbar(lutf, orient="vertical", command=self.tree.yview)
            self.tree.configure(yscrollcommand=sy.set)
            self.tree.pack(side="left", fill="both", expand=True, pady=(6, 0))
            sy.pack(side="right", fill="y", pady=(6, 0))
            self.tree.bind("<Double-1>", self.edit_lut_row)

            acts = ttk.Frame(self.tab_cfg)
            acts.pack(fill="x", pady=4)
            ttk.Button(acts, text="Read Settings", command=self.read_device).pack(side="left", padx=3)
            ttk.Button(acts, text="Restore Defaults", command=self.restore).pack(side="left", padx=3)
            ttk.Button(acts, text="Save to Device", command=self.save_device).pack(side="left", padx=3)

            fw = ttk.LabelFrame(self.tab_cfg, text="Firmware upload (.bin via ST-Link)", padding=8)
            fw.pack(fill="x", pady=6)
            ttk.Entry(fw, textvariable=self.bin_path).pack(side="left", fill="x", expand=True)
            ttk.Button(fw, text="Browse…", command=self.browse_bin).pack(side="left", padx=6)
            ttk.Button(fw, text="Flash", command=self.flash_bin).pack(side="left")

            self.fill_lut()
            self.refresh_presets()

        def _on_delay(self, _value: str = "") -> None:
            self.delay_lbl.config(text=f"{int(round(float(self.delay.get())))} ms")

        def _delay_ms(self) -> int:
            return max(0, min(20, int(round(float(self.delay.get())))))

        def on_tab(self, _evt=None) -> None:
            if self.nb.select() == str(self.tab_test):
                if self.dev:
                    try:
                        self.dev.exit_config()
                    except Exception:
                        pass
                    self.dev_status.set("Config: connected, Mode 1 (HID on)")
                self.start_hid_listen()
                self.status.set("Mode 1: BOOT on ESP or Scan. Keystrokes stay in this window.")
            else:
                self.stop_hid_listen()
                if self.dev:
                    try:
                        self.dev.enter_config()
                    except Exception:
                        pass
                    self.dev_status.set(f"Config: connected {self.cfg_port.get()}  (HID paused)")
                self.status.set("Mode 2: Read / edit / Save. HID typing is paused while connected.")

        def on_refresh(self) -> None:
            # Do not ping serial ports here — opening the ESP CH340 resets it.
            self.stop_hid_listen()
            self.refresh_ports(probe=False)
            if self.nb.select() == str(self.tab_test):
                self.start_hid_listen()
            self.status.set("Refreshed HID grab and serial list.")

        def refresh_ports(self, probe: bool = False) -> None:
            ports = serial_ports()
            self.esp_combo["values"] = ports
            self.cfg_combo["values"] = ports
            hid, name, vid, pid = find_hid()
            if hid:
                self.hid_status.set(f"HID: {name}  {vid:04X}:{pid:04X}  {hid}")
            else:
                self.hid_status.set("HID: not found — plug STM Mini-USB (BarcodeHID)")
            if probe:
                skip = self.esp_port.get()
                ordered = [p for p in ports if p != skip] + [p for p in ports if p == skip]
                stm = next((p for p in ordered if probe_port(p)), "")
                if stm:
                    self.cfg_port.set(stm)
                others = [p for p in ports if p != stm]
                if others and self.esp_port.get() not in others:
                    self.esp_port.set(others[-1])
            else:
                if ports and self.esp_port.get() not in ports:
                    skip = self.cfg_port.get()
                    others = [p for p in ports if p != skip]
                    self.esp_port.set(others[-1] if others else ports[-1])
                if ports and self.cfg_port.get() not in ports:
                    others = [p for p in ports if p != self.esp_port.get()]
                    if others:
                        self.cfg_port.set(others[0])

        def close_esp(self) -> None:
            self._esp_ready = False
            if self.esp_ser is not None:
                try:
                    self.esp_ser.close()
                except Exception:
                    pass
                self.esp_ser = None

        def ensure_esp(self):
            port = self.esp_port.get()
            if not port:
                raise RuntimeError("Select the ESP serial port")
            if self.esp_ser is not None and self.esp_ser.is_open and self.esp_ser.port == port:
                return self.esp_ser
            self.close_esp()
            self.esp_ser = open_tty(port)
            wait_esp_ready(self.esp_ser)
            self._esp_ready = True
            return self.esp_ser

        def start_hid_listen(self) -> None:
            path, *_ = find_hid()
            if self.hid_grab is not None and path and getattr(self.hid_grab, "path", None) == path:
                return
            self.stop_hid_listen()
            if not path:
                self.match.config(text="HID not found — plug STM Mini-USB")
                return
            try:
                self.hid_grab = HidGrab(path, grab=True)
            except PermissionError:
                self.match.config(text="Need sudo or group input for /dev/input")
                return
            except OSError as exc:
                self.match.config(text=str(exc))
                return
            self._poll_hid()

        def stop_hid_listen(self) -> None:
            if self._hid_after is not None:
                try:
                    self.after_cancel(self._hid_after)
                except Exception:
                    pass
                self._hid_after = None
            if self.hid_grab is not None:
                try:
                    self.hid_grab.close()
                except Exception:
                    pass
                self.hid_grab = None

        def _poll_hid(self) -> None:
            if self.hid_grab is None:
                return
            added = False
            try:
                for ch in self.hid_grab.read_chars():
                    self._hid_raw.append(ch)
                    added = True
            except Exception as exc:
                self.match.config(text=str(exc))
                self._hid_after = self.after(50, self._poll_hid)
                return
            if added:
                received = "".join(self._hid_raw)
                self.got.delete("1.0", "end")
                self.got.insert("1.0", show_hid(received))
                self.got.see("end")
                self.match.config(text=f"{len(received)} characters from HID")
            self._hid_after = self.after(15, self._poll_hid)

        def clear_hid(self) -> None:
            self._hid_raw.clear()
            self.got.delete("1.0", "end")
            self.match.config(text="BOOT on ESP or Scan.")

        def bridge_scan(self) -> None:
            if self.nb.select() != str(self.tab_test):
                self.nb.select(self.tab_test)
                self.update_idletasks()
                self.on_tab()
            if not find_hid()[0]:
                messagebox.showerror("Scan", "STM HID not found. Plug Mini-USB.")
                return
            self.start_hid_listen()
            self.clear_hid()
            self.match.config(text="Scanning…")
            try:
                ser = self.ensure_esp()
                ser.write(b"s")
                ser.flush()
            except Exception as exc:
                messagebox.showerror("Scan", str(exc))

        def refresh_presets(self) -> None:
            files = sorted(p.name for p in PRESETS.glob("*.csv")) if PRESETS.exists() else []
            self.preset_box["values"] = files
            if files and self.preset.get() not in files:
                self.preset.set(files[0])

        def fill_lut(self) -> None:
            dflt = default_lut()
            self.tree.delete(*self.tree.get_children())
            for i, m in enumerate(self.lut):
                if self.filter_mod.get() and m == dflt[i]:
                    continue
                self.tree.insert(
                    "",
                    "end",
                    iid=str(i),
                    values=(f"0x{i:02X}", ascii_label(i), f"0x{m:02X}", action_label(m)),
                )

        def edit_lut_row(self, _evt=None) -> None:
            sel = self.tree.selection()
            if not sel:
                return
            i = int(sel[0])
            win = tk.Toplevel(self)
            win.title(f"Map 0x{i:02X}  {ascii_label(i)}")
            win.transient(self)
            cur = self.lut[i]
            kind = {0: "Ignore", 0x0A: "Enter", 0x09: "Tab"}.get(cur, "Printable")
            var = tk.StringVar(value=kind)
            ttk.Label(win, text="HID target").pack(padx=12, pady=(10, 4))
            ttk.Combobox(
                win, textvariable=var, values=("Ignore", "Enter", "Tab", "Printable"), state="readonly", width=16
            ).pack(padx=12)
            ch = tk.StringVar(value=chr(i) if 0x20 <= i <= 0x7E else "A")
            ttk.Entry(win, textvariable=ch, width=8).pack(pady=8)

            def apply() -> None:
                v = var.get()
                if v == "Ignore":
                    self.lut[i] = 0
                elif v == "Enter":
                    self.lut[i] = 0x0A
                elif v == "Tab":
                    self.lut[i] = 0x09
                else:
                    self.lut[i] = ord((ch.get()[:1] or " ")) & 0xFF
                self.fill_lut()
                win.destroy()

            ttk.Button(win, text="OK", command=apply).pack(pady=(0, 10))

        def load_preset(self) -> None:
            name = self.preset.get()
            path = PRESETS / name
            if path.exists():
                self.lut = read_csv(path)
            elif "enter" in name:
                self.lut = preset_enter_delimiters()
            else:
                self.lut = default_lut()
            self.fill_lut()
            self.status.set(f"Loaded {name} (Save to Device to persist)")

        def import_csv(self) -> None:
            path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("All", "*.*")])
            if path:
                self.lut = read_csv(Path(path))
                self.fill_lut()

        def export_csv(self) -> None:
            path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if path:
                write_csv(Path(path), self.lut)

        def connect(self) -> None:
            port = self.cfg_port.get()
            if not port:
                self.refresh_ports(probe=True)
                port = self.cfg_port.get()
            if not port:
                messagebox.showerror("Connect", "No STM config port. Plug J6 USB-UART.")
                return
            try:
                self.disconnect(silent=True)
                self.cfg_ser = open_tty(port)
                self.dev = Device(self.cfg_ser)
                if not self.dev.ping():
                    raise RuntimeError("no BKCFG ping — pick the STM J6 adapter, not the ESP")
                if self.nb.select() == str(self.tab_cfg):
                    self.dev.enter_config()
                    self.dev_status.set(f"Config: connected {port}  (HID paused)")
                else:
                    self.dev_status.set(f"Config: connected {port}  (Mode 1, HID on)")
                self.status.set(f"Connected {port}")
            except Exception as exc:
                self.disconnect(silent=True)
                messagebox.showerror("Connect", str(exc))

        def disconnect(self, silent: bool = False) -> None:
            if self.dev:
                try:
                    self.dev.exit_config()
                except Exception:
                    pass
            self.dev = None
            if self.cfg_ser:
                try:
                    self.cfg_ser.close()
                except Exception:
                    pass
            self.cfg_ser = None
            if not silent:
                self.dev_status.set("Config: not connected")
                self.status.set("Disconnected. STM is a HID keyboard.")

        def read_device(self) -> None:
            if not self.dev:
                messagebox.showinfo("Read Settings", "Connect J6 first.")
                return
            try:
                u = self.dev.get_uart()
                self.baud.set(str(u["baud"]))
                self.parity.set({0: "None", 1: "Even", 2: "Odd"}.get(u["parity"], "None"))
                self.stop.set(str(u["stop"] or 1))
                self.delay.set(float(u["delay_ms"]))
                self._on_delay()
                self.lut = self.dev.get_lut()
                self.fill_lut()
                self.status.set(f"Read {u['baud']} delay {u['delay_ms']} ms")
            except Exception as exc:
                messagebox.showerror("Read Settings", str(exc))

        def restore(self) -> None:
            self.lut = default_lut()
            self.baud.set("115200")
            self.parity.set("None")
            self.stop.set("1")
            self.delay.set(5.0)
            self._on_delay()
            self.fill_lut()
            if self.dev:
                try:
                    self.dev.restore()
                except Exception as exc:
                    messagebox.showerror("Restore Defaults", str(exc))
                    return
            self.status.set("Appendix A defaults (Save to Device to persist)")

        def save_device(self) -> None:
            if not self.dev:
                messagebox.showinfo("Save to Device", "Connect J6 first.")
                return
            par = {"None": 0, "Even": 1, "Odd": 2}[self.parity.get()]
            try:
                self.dev.set_uart(int(self.baud.get()), par, int(self.stop.get()), self._delay_ms())
                self.dev.set_lut(self.lut)
                self.dev.commit()
                messagebox.showinfo("Save to Device", "Saved to internal Flash.")
            except Exception as exc:
                messagebox.showerror("Save to Device", str(exc))

        def browse_bin(self) -> None:
            path = filedialog.askopenfilename(filetypes=[("Binary", "*.bin"), ("All", "*.*")])
            if path:
                self.bin_path.set(path)

        def flash_bin(self) -> None:
            path = self.bin_path.get()
            if not path:
                messagebox.showerror("Flash", "Select a .bin")
                return
            self.disconnect(silent=True)
            try:
                subprocess.run(["st-flash", "--reset", "write", path, "0x08000000"], check=True)
                messagebox.showinfo("Flash", "Written. Re-plug Mini-USB if HID does not return, then Refresh.")
                self.after(1500, lambda: self.refresh_ports(probe=False))
            except FileNotFoundError:
                messagebox.showerror("Flash", "st-flash not found")
            except Exception as exc:
                messagebox.showerror("Flash", str(exc))

        def on_close(self) -> None:
            self.stop_hid_listen()
            self.close_esp()
            self.disconnect(silent=True)
            self.destroy()

    App().mainloop()


def main() -> None:
    p = argparse.ArgumentParser(description="UART-HID demo + configurator")
    p.add_argument("--cli", action="store_true")
    p.add_argument("--port", help="ESP serial port for --cli")
    args = p.parse_args()
    if args.cli:
        raise SystemExit(run_cli(args.port))
    run_gui()


if __name__ == "__main__":
    main()
