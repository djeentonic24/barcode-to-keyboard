#!/usr/bin/env python3
"""Fake barcode scanner: dump an AAMVA-like UART burst to a COM port."""
import argparse
import time

try:
    import serial
except ImportError:
    raise SystemExit("pip install pyserial")

# Typical AAMVA header + delimiters (CR/LF/GS) + printable payload.
SAMPLE = (
    b"@\n\x1e\rANSI 636000090002DL00410288ZV03290015DLDAQ12345678\n"
    b"DCSDOE\nDACJOHN\nDADNONE\n"
    b"DBB01011990\nDBA01012030\n"
    b"DBC1\nDAU070 IN\n"
    b"DAG123 MAIN ST\nDAIANYTOWN\nDAJCA\nDAK902100000\n"
    b"\x1d"
    b"ZV\nZVA123\r"
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("port", help="COM port of USB-UART (scanner TX)")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--gap", type=float, default=1.0, help="seconds between scans")
    p.add_argument("--chunk", type=int, default=0, help="0 = one burst, else bytes per write")
    args = p.parse_args()

    ser = serial.Serial(args.port, args.baud, timeout=1)
    time.sleep(0.2)
    for i in range(args.repeat):
        if args.chunk <= 0:
            ser.write(SAMPLE)
            ser.flush()
        else:
            for n in range(0, len(SAMPLE), args.chunk):
                ser.write(SAMPLE[n : n + args.chunk])
                ser.flush()
        print(f"sent scan {i + 1}: {len(SAMPLE)} bytes")
        if i + 1 < args.repeat:
            time.sleep(args.gap)
    ser.close()


if __name__ == "__main__":
    main()
