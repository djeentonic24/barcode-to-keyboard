#!/usr/bin/env python3
"""Ask the ESP to emit one AAMVA burst on GPIO17."""
from __future__ import annotations

import argparse
import sys

try:
    import serial
except ImportError:
    raise SystemExit("pip install pyserial")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("port", nargs="?", default="/dev/ttyUSB1")
    args = p.parse_args()
    ser = serial.Serial()
    ser.port = args.port
    ser.baudrate = 115200
    ser.timeout = 0.2
    ser.dsrdtr = False
    ser.rtscts = False
    ser.dtr = False
    ser.rts = False
    ser.open()
    try:
        ser.reset_input_buffer()
        ser.write(b"s")
        ser.flush()
        sys.stdout.write(ser.read(256).decode("utf-8", "replace"))
    finally:
        ser.close()


if __name__ == "__main__":
    main()
