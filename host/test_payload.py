from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from host.device_link import pack, unpack
from host.lut_io import default_lut, read_csv, write_csv
from host.payload import AAMVA_FIELDS, EXPECTED_HID, SAMPLE, apply_lut, selfcheck


def test_selfcheck() -> None:
    selfcheck()


def test_lut_roundtrip() -> None:
    assert apply_lut(SAMPLE) == EXPECTED_HID
    assert apply_lut(b"\x00\x01\x7f") == ""
    assert apply_lut(b"A\nB\rC") == "A\nB\nC"
    assert apply_lut(b"\x1c\x1d\x1e\x1f") == "\t\t\t\t"


def test_csv_roundtrip(tmp_path: Path | None = None) -> None:
    path = (tmp_path or Path("/tmp")) / "lut.csv"
    lut = default_lut()
    lut[0x1C] = 0x0A
    write_csv(path, lut)
    assert read_csv(path) == lut


def test_config_frame() -> None:
    frame = pack(1, 7, b"")
    got = unpack(frame)
    assert got == (1, 7, b"")
    assert unpack(frame[:-1] + bytes([frame[-1] ^ 1])) is None


def test_aamva_fields() -> None:
    assert AAMVA_FIELDS["DAC"] == "JOHN"
    assert AAMVA_FIELDS["DCS"] == "DOE"
    assert AAMVA_FIELDS["DAQ"] == "12345678"
    assert "JOHN" in EXPECTED_HID


if __name__ == "__main__":
    test_selfcheck()
    test_lut_roundtrip()
    test_csv_roundtrip()
    test_config_frame()
    test_aamva_fields()
    print("ok")
