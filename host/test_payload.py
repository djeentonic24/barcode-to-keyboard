from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from host.payload import AAMVA_FIELDS, EXPECTED_HID, SAMPLE, apply_lut, selfcheck


def test_selfcheck() -> None:
    selfcheck()


def test_lut_roundtrip() -> None:
    assert apply_lut(SAMPLE) == EXPECTED_HID
    assert apply_lut(b"\x00\x01\x7f") == ""
    assert apply_lut(b"A\nB\rC") == "A\nB\nC"
    assert apply_lut(b"\x1c\x1d\x1e\x1f") == "\t\t\t\t"


def test_aamva_fields() -> None:
    assert AAMVA_FIELDS["DAC"] == "JOHN"
    assert AAMVA_FIELDS["DCS"] == "DOE"
    assert AAMVA_FIELDS["DAQ"] == "12345678"
    assert "JOHN" in EXPECTED_HID


if __name__ == "__main__":
    test_selfcheck()
    test_lut_roundtrip()
    test_aamva_fields()
    print("ok")
