"""Linux evdev helpers for the STM32 BarcodeHID keyboard."""
from __future__ import annotations

import fcntl
import os
import struct
import time
from typing import Callable, Iterator

VID = 0x0483
PIDS = {0x5711, 0x5740}
NAME_HINTS = ("barcodehid",)

EV_KEY = 0x01
KEY_DOWN = 1
EVIOCGRAB = 0x40044590
EVENT_FMT = "llHHI"
EVENT_SIZE = struct.calcsize(EVENT_FMT)

SHIFT_KEYS = {42, 54}

KEYMAP = {
    2: "1",
    3: "2",
    4: "3",
    5: "4",
    6: "5",
    7: "6",
    8: "7",
    9: "8",
    10: "9",
    11: "0",
    12: "-",
    13: "=",
    14: "",
    15: "\t",
    16: "q",
    17: "w",
    18: "e",
    19: "r",
    20: "t",
    21: "y",
    22: "u",
    23: "i",
    24: "o",
    25: "p",
    26: "[",
    27: "]",
    28: "\n",
    30: "a",
    31: "s",
    32: "d",
    33: "f",
    34: "g",
    35: "h",
    36: "j",
    37: "k",
    38: "l",
    39: ";",
    40: "'",
    41: "`",
    43: "\\",
    44: "z",
    45: "x",
    46: "c",
    47: "v",
    48: "b",
    49: "n",
    50: "m",
    51: ",",
    52: ".",
    53: "/",
    57: " ",
}

SHIFT_MAP = {
    "1": "!",
    "2": "@",
    "3": "#",
    "4": "$",
    "5": "%",
    "6": "^",
    "7": "&",
    "8": "*",
    "9": "(",
    "0": ")",
    "-": "_",
    "=": "+",
    "[": "{",
    "]": "}",
    ";": ":",
    "'": '"',
    "`": "~",
    "\\": "|",
    ",": "<",
    ".": ">",
    "/": "?",
}


def parse_proc_devices() -> list[dict]:
    handlers: list[dict] = []
    block: dict = {}
    path = "/proc/bus/input/devices"
    if not os.path.exists(path):
        return handlers
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                if block:
                    handlers.append(block)
                block = {}
                continue
            if line.startswith("I: "):
                parts = dict(p.split("=", 1) for p in line[3:].split() if "=" in p)
                block["vendor"] = int(parts.get("Vendor", "0"), 16)
                block["product"] = int(parts.get("Product", "0"), 16)
            elif line.startswith("N: Name="):
                block["name"] = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("H: Handlers="):
                block["handlers"] = line.split("=", 1)[1].split()
    if block:
        handlers.append(block)
    return handlers


def find_hid() -> tuple[str | None, str, int, int]:
    for d in parse_proc_devices():
        name = d.get("name", "")
        vid = d.get("vendor", 0)
        pid = d.get("product", 0)
        evs = [h for h in d.get("handlers", []) if h.startswith("event")]
        if not evs:
            continue
        is_kbd = "kbd" in d.get("handlers", [])
        if not is_kbd:
            continue
        if (vid == VID and pid in PIDS and "barcodehid" in name.lower()) or any(
            h in name.lower() for h in NAME_HINTS
        ):
            return f"/dev/input/{evs[0]}", name, vid, pid
    return None, "", 0, 0


def decode_key(code: int, value: int, shift: bool) -> tuple[bool, str]:
    """Returns (new_shift, text_or_empty)."""
    if code in SHIFT_KEYS:
        return value != 0, ""
    if value != KEY_DOWN:
        return shift, ""
    ch = KEYMAP.get(code)
    if ch is None:
        return shift, ""
    if not ch:
        return shift, ""
    if shift and ch.isalpha():
        return shift, ch.upper()
    if shift and ch in SHIFT_MAP:
        return shift, SHIFT_MAP[ch]
    return shift, ch


class HidGrab:
    def __init__(self, path: str, grab: bool = True) -> None:
        self.path = path
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        self.grabbed = False
        if grab:
            try:
                fcntl.ioctl(self.fd, EVIOCGRAB, 1)
                self.grabbed = True
            except OSError:
                self.grabbed = False
        self.shift = False

    def read_chars(self) -> Iterator[str]:
        while True:
            try:
                raw = os.read(self.fd, EVENT_SIZE)
            except BlockingIOError:
                return
            if len(raw) < EVENT_SIZE:
                return
            _sec, _usec, etype, code, value = struct.unpack(EVENT_FMT, raw)
            if etype != EV_KEY:
                continue
            self.shift, text = decode_key(code, value, self.shift)
            if text:
                yield text

    def collect(self, seconds: float, idle: float = 0.35) -> str:
        buf: list[str] = []
        deadline = time.time() + seconds
        last = time.time()
        while time.time() < deadline:
            got = False
            for ch in self.read_chars():
                buf.append(ch)
                got = True
                last = time.time()
            if buf and (time.time() - last) > idle:
                break
            time.sleep(0.01)
        return "".join(buf)

    def close(self) -> None:
        if self.grabbed:
            try:
                fcntl.ioctl(self.fd, EVIOCGRAB, 0)
            except OSError:
                pass
        os.close(self.fd)

    def __enter__(self) -> "HidGrab":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
