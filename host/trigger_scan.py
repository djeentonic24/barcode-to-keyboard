#!/usr/bin/env python3
"""Ask the ESP to emit one AAMVA burst on GPIO17."""
from __future__ import annotations

import argparse
import sys
import time

try:
    import serial
except ImportError:
    raise SystemExit("pip install pyserial")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("port", nargs="?", default="/dev/ttyUSB1")
    args = p.parse_args()
    ser = serial.Serial(args.port, 115200, timeout=1)
    time.sleep(0.2)
    ser.reset_input_buffer()
    ser.write(b"s")
    ser.flush()
    time.sleep(0.4)
    sys.stdout.write(ser.read(512).decode("utf-8", "replace"))
    ser.close()


if __name__ == "__main__":
    main()
