"""F4VE config link: 64-byte frames on USART1 (J6). Same payload planned for HID Feature Reports on C071."""
from __future__ import annotations

import struct
import time

MAGIC = b"\xA5\x5A"
FRAME = 64
CMD_PING = 1
CMD_ENTER = 2
CMD_EXIT = 3
CMD_GET_UART = 4
CMD_SET_UART = 5
CMD_GET_LUT = 6
CMD_SET_LUT = 7
CMD_RESTORE = 8
CMD_COMMIT = 9
ACK = 0x80


def crc16(data: bytes) -> int:
    c = 0xFFFF
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c & 0xFFFF


def pack(cmd: int, seq: int, payload: bytes = b"") -> bytes:
    if len(payload) > 56:
        raise ValueError("payload too long")
    raw = bytearray(FRAME)
    raw[0:2] = MAGIC
    raw[2] = cmd & 0xFF
    raw[3] = seq & 0xFF
    raw[4] = len(payload)
    raw[5 : 5 + len(payload)] = payload
    struct.pack_into("<H", raw, 62, crc16(bytes(raw[:62])))
    return bytes(raw)


def unpack(frame: bytes) -> tuple[int, int, bytes] | None:
    if len(frame) != FRAME or frame[0:2] != MAGIC:
        return None
    if crc16(frame[:62]) != struct.unpack_from("<H", frame, 62)[0]:
        return None
    n = frame[4]
    if n > 56:
        return None
    return frame[2], frame[3], bytes(frame[5 : 5 + n])


class Device:
    def __init__(self, ser) -> None:
        self.ser = ser
        self.seq = 0

    def transact(self, cmd: int, payload: bytes = b"", timeout: float = 0.6) -> bytes:
        self.seq = (self.seq + 1) & 0xFF
        self.ser.reset_input_buffer()
        self.ser.write(pack(cmd, self.seq, payload))
        self.ser.flush()
        deadline = time.time() + timeout
        buf = bytearray()
        while time.time() < deadline:
            buf.extend(self.ser.read(self.ser.in_waiting or 1))
            while len(buf) >= FRAME:
                frame = bytes(buf[:FRAME])
                del buf[:FRAME]
                got = unpack(frame)
                if not got:
                    continue
                rcmd, seq, pl = got
                if seq == self.seq and rcmd == (cmd | ACK):
                    if not pl:
                        raise RuntimeError("empty ack")
                    if pl[0] != 0:
                        raise RuntimeError(f"device error {pl[0]}")
                    return pl[1:]
        raise TimeoutError("no ack from device")

    def ping(self) -> bool:
        try:
            return self.transact(CMD_PING) == b"BKCFG"
        except (TimeoutError, RuntimeError, OSError):
            return False

    def enter_config(self) -> None:
        self.transact(CMD_ENTER)

    def exit_config(self) -> None:
        self.transact(CMD_EXIT)

    def get_uart(self) -> dict:
        pl = self.transact(CMD_GET_UART)
        baud, parity, stop, delay = struct.unpack_from("<IBBB", pl)
        return {"baud": baud, "parity": parity, "stop": stop, "delay_ms": delay}

    def set_uart(self, baud: int, parity: int, stop: int, delay_ms: int) -> None:
        self.transact(CMD_SET_UART, struct.pack("<IBBB", baud, parity, stop, delay_ms))

    def get_lut(self) -> list[int]:
        lut: list[int] = []
        for off in range(0, 256, 32):
            lut.extend(self.transact(CMD_GET_LUT, bytes([off])))
        return lut[:256]

    def set_lut(self, lut: list[int]) -> None:
        blob = bytes(lut[i] & 0xFF for i in range(256))
        for off in range(0, 256, 32):
            self.transact(CMD_SET_LUT, bytes([off]) + blob[off : off + 32])

    def restore(self) -> None:
        self.transact(CMD_RESTORE)

    def commit(self) -> None:
        self.transact(CMD_COMMIT, timeout=2.0)


def probe_port(port: str, baud: int = 115200) -> bool:
    try:
        import serial
    except ImportError:
        return False
    try:
        ser = serial.Serial(port, baud, timeout=0.15)
    except OSError:
        return False
    try:
        return Device(ser).ping()
    except Exception:
        return False
    finally:
        ser.close()
