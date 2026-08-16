"""Canonical AAMVA demo payload and TZ Appendix A LUT.

Firmware headers are generated from this file (scripts/gen_assets.py).
"""

from __future__ import annotations

# Raw scanner burst (PDF417 / AAMVA DL). Control bytes: LF, CR, RS, GS.
SAMPLE = (
    b"@\n\x1e\rANSI 636000090002DL00410288ZV03290015DLDAQ12345678\n"
    b"DCSDOE\nDACJOHN\nDADNONE\n"
    b"DBB01011990\nDBA01012030\n"
    b"DBC1\nDAU070 IN\n"
    b"DAG123 MAIN ST\nDAIANYTOWN\nDAJCA\nDAK902100000\n"
    b"\x1d"
    b"ZV\nZVA123\r"
)

# Appendix A default LUT: 0 = drop, else ASCII fed to HID Keyboard.write()
# 0x0A/0x0D -> Enter, 0x1C-0x1F -> Tab, 0x20-0x7E -> themselves.
LUT = [0] * 256
for c in range(0x20, 0x7F):
    LUT[c] = c
LUT[0x0A] = ord("\n")
LUT[0x0D] = ord("\n")
LUT[0x1C] = ord("\t")
LUT[0x1D] = ord("\t")
LUT[0x1E] = ord("\t")
LUT[0x1F] = ord("\t")


def apply_lut(data: bytes) -> str:
    out: list[str] = []
    for b in data:
        m = LUT[b]
        if m:
            out.append(chr(m))
    return "".join(out)


def aamva_field(data: bytes, tag: str) -> str:
    """Extract an AAMVA data element (3-letter tag)."""
    tb = tag.encode("ascii")
    idx = 0
    while True:
        i = data.find(tb, idx)
        if i < 0:
            return ""
        prev = data[i - 1] if i else 0
        # Element starts after a delimiter, start-of-record, or 'DL' header (DLDAQ).
        ok = (
            i == 0
            or prev in (0x0A, 0x0D, 0x1C, 0x1D, 0x1E, 0x1F, 0x40)  # @ header
            or (prev == ord("L") and i >= 2 and data[i - 2] == ord("D"))
        )
        if ok:
            j = i + 3
            val = bytearray()
            while j < len(data):
                c = data[j]
                if c in (0x0A, 0x0D, 0x1C, 0x1D, 0x1E, 0x1F):
                    break
                if 0x20 <= c <= 0x7E:
                    val.append(c)
                j += 1
            return val.decode("ascii")
        idx = i + 1


EXPECTED_HID = apply_lut(SAMPLE)

AAMVA_FIELDS = {
    "DAQ": aamva_field(SAMPLE, "DAQ"),
    "DCS": aamva_field(SAMPLE, "DCS"),
    "DAC": aamva_field(SAMPLE, "DAC"),
    "DAD": aamva_field(SAMPLE, "DAD"),
    "DAG": aamva_field(SAMPLE, "DAG"),
    "DAI": aamva_field(SAMPLE, "DAI"),
    "DAJ": aamva_field(SAMPLE, "DAJ"),
}


def selfcheck() -> None:
    assert AAMVA_FIELDS["DAC"] == "JOHN", AAMVA_FIELDS
    assert AAMVA_FIELDS["DCS"] == "DOE", AAMVA_FIELDS
    assert AAMVA_FIELDS["DAQ"] == "12345678", AAMVA_FIELDS
    assert AAMVA_FIELDS["DAG"] == "123 MAIN ST", AAMVA_FIELDS
    assert SAMPLE[0] == ord("@")
    assert b"\x1e" in SAMPLE and b"\x1d" in SAMPLE
    assert EXPECTED_HID.startswith("@\n\t\nANSI")
    assert "JOHN" in EXPECTED_HID and "DOE" in EXPECTED_HID
    assert "\n" in EXPECTED_HID and "\t" in EXPECTED_HID
    # dropped: nothing from 0x00-0x09 besides mapped ones
    assert all(LUT[b] == 0 for b in range(0x00, 0x0A))


if __name__ == "__main__":
    selfcheck()
    print(f"payload {len(SAMPLE)} bytes")
    print("fields", AAMVA_FIELDS)
    print("--- expected HID ---")
    print(EXPECTED_HID.replace("\t", "→TAB→").replace("\n", "→ENT→\n"))
