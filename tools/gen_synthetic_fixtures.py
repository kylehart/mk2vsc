#!/usr/bin/env python3
"""Regenerate the synthetic fixtures under fixtures/synthetic/ from corpus blocks.

    python tools/gen_synthetic_fixtures.py          # write the three files (idempotent)
    python tools/gen_synthetic_fixtures.py --check  # exit 1 if a file on disk differs from what this produces

These files are not device downloads.  They exercise two file shapes the corpus does not hold, built from
bytes the corpus does hold, with pointers and checksums recomputed by ``mk2vsc.sections`` (the same code the
writer uses):

* ``single-unit .rvsc``: the byte prefix of a two-inverter device download up to its second block.  A section's
  pointer is the absolute start of the next section, so the first block's pointer already equals its own end and
  nothing is rewritten; the file is the prefix, byte for byte (tests/test_short_files.py proves that on the
  corpus file).  It carries System A's first inverter and its flag byte f4 as downloaded.  Real single-unit
  files carry flag f0 / e0 (docs/FORMAT.md 3.1); the flag byte is not read by anything that decodes settings.
* ``three-phase .rvms`` (3 and 6 units): one ESS block of System A cloned n times with distinct pseudonymised
  serials and the per-slot bytes set to the pattern observed on real three-phase files (docs/FORMAT.md 3.1):
  +0x35 = 4 * (index mod 3) (00 / 04 / 08), +0x37 = index, flag low nibble = 8 + (index mod 3) (e8 / e9 / ea).
  Every block carries the same 1152-byte assistant record; a real three-phase system carries different records
  per unit, so these files say nothing about assistant bodies.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mk2vsc.sections import RvmsFile, SECTION_DATA          # noqa: E402
from mk2vsc.units import unit_blocks, units_by_serial, OFF_SLOT_A, OFF_ASSISTANT_FLAG, OFF_SLOT_B, OFF_SERIAL, PREFIX_LEN  # noqa: E402

FIXTURES = os.path.join(ROOT, "fixtures")
SINGLE_SOURCE = "system_a/system_a_2026-07-20_download_bare_deviceform_1.rvms"
THREE_PHASE_SOURCE = "system_a/system_a_2026-09-03_download_ess_deviceform_1.rvms"
THREE_PHASE_SOURCE_SERIAL = "HQ0000A0001"                      # the block with the 1152-byte record, slot (00, 00), flag e4

OUTPUTS = {
    "synthetic/system_a_2026-07-20_synthetic_bare_deviceform_1.rvsc": ("single", None),
    "synthetic/system_a_2026-09-03_synthetic_ess_deviceform_1.rvms": ("three_phase", 3),
    "synthetic/system_a_2026-09-03_synthetic_ess_deviceform_2.rvms": ("three_phase", 6),
}


def _read(rel: str) -> bytes:
    with open(os.path.join(FIXTURES, rel), "rb") as fh:
        return fh.read()


def single_unit(data: bytes) -> bytes:
    """The two-block file with its second ``BareSettingData`` dropped; pointers and checksums recomputed."""
    f = RvmsFile.parse(data)
    assert len(f.unit_sections) == 2
    keep = [s for s in f.sections if not s.is_unit] + [f.unit_sections[0]]
    return RvmsFile(magic_raw=f.magic_raw, sections=keep, length=0).rebuild().to_bytes()


def three_phase(data: bytes, source_serial: str, n: int) -> bytes:
    """``n`` clones of one block with serials HQ0000A0003.., phase bytes cycling L1/L2/L3 and unit index 0..n-1."""
    f = RvmsFile.parse(data)
    src = units_by_serial(f)[source_serial]
    assert src.slot == (0, 0) and src.assistant_flag == 0xE4 and not src.is_upload_form
    payloads = []
    for i in range(n):
        p = bytearray(src.section.payload)
        phase = i % 3
        p[OFF_SLOT_A - PREFIX_LEN] = 4 * phase
        p[OFF_ASSISTANT_FLAG - PREFIX_LEN] = 0xE8 + phase
        p[OFF_SLOT_B - PREFIX_LEN] = i
        serial = f"HQ0000A{3 + i:04d}".encode()
        assert len(serial) == 11
        p[OFF_SERIAL - PREFIX_LEN: OFF_SERIAL - PREFIX_LEN + 11] = serial
        payloads.append(bytes(p))
    head = [s for s in f.sections if not s.is_unit]
    from mk2vsc.sections import Section
    sections = head + [Section(start=0, name=SECTION_DATA, next_ptr=0, payload=p, stored_checksum=0, raw=b"") for p in payloads]
    return RvmsFile(magic_raw=f.magic_raw, sections=sections, length=0).rebuild().to_bytes()


def build() -> dict:
    out = {}
    for rel, (kind, n) in OUTPUTS.items():
        if kind == "single":
            out[rel] = single_unit(_read(SINGLE_SOURCE))
        else:
            out[rel] = three_phase(_read(THREE_PHASE_SOURCE), THREE_PHASE_SOURCE_SERIAL, n)
    return out


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for rel, data in build().items():
        path = os.path.join(FIXTURES, rel)
        if check:
            on_disk = open(path, "rb").read() if os.path.exists(path) else None
            if on_disk != data:
                stale.append(rel)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        f = RvmsFile.parse(data)
        print(f"wrote {rel}: {len(data)} bytes, {len(unit_blocks(f))} inverter(s), checksums {'OK' if f.all_checksums_ok else 'BAD'}")
    if stale:
        print("gen_synthetic_fixtures: STALE: " + ", ".join(stale) + " (run without --check to rewrite)")
        return 1
    if check:
        print("gen_synthetic_fixtures: fixtures/synthetic/ is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
