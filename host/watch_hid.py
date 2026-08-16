#!/usr/bin/env python3
"""CLI: grab STM BarcodeHID and print LUT-mapped text."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from host.hiddecode import HidGrab, find_hid  # noqa: E402


def main() -> None:
    path, name, vid, pid = find_hid()
    if not path:
        raise SystemExit("STM HID not found (plug Mini-USB, device name BarcodeHID)")
    print(f"{name}  {vid:04X}:{pid:04X}  {path}")
    try:
        grab = HidGrab(path, grab=True)
    except PermissionError:
        raise SystemExit("need /dev/input access: sudo or usermod -aG input $USER")
    print("waiting for scan  Ctrl-C to quit")
    try:
        while True:
            for ch in grab.read_chars():
                sys.stdout.write(ch)
                sys.stdout.flush()
            import time

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        grab.close()


if __name__ == "__main__":
    main()
