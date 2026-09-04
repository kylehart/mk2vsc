"""
EXPERIMENTAL: convert a device-form download into the GUI's *upload form*, the byte layout VEConfigure /
VE.Bus System Configurator writes when it exports a file for Remote VEConfigure upload.

Why anyone would want this: GUI-authored upload-form files install assistants that RUN; our device-form
grafts install assistants that store and never start.  One hypothesis (docs/ESS_INJECTION.md, H2) was
that the upload form itself is what triggers the device-side install procedure.  This transform was
built to test that.  Result on 2026-08-13: the device ACCEPTED a transformed file (after two fixes that
this module now contains), stored the configuration, and the system still did not start.  The
hypothesis is weakened, not dead: the target system had a broken BMS bus at the time (H3).

Derivation.  We hold one matched pair: the installer's real GUI export for Papaya (upload form) and
Papaya's own device download taken after that upload succeeded (device form).  Per block, upload =

    raw[0x00:0x45]                        name, pointer, header, slot/flag bytes, serial (unchanged)
    BLOB12 + u32 export_timestamp         16 bytes; BLOB12 is identical in every GUI export we hold
    4 zero bytes
    u32 save_timestamp                    a few seconds before the export timestamp in the real export
    raw[0x53:assistant_area]              4 zeros, 0x0180, the 190 settings (unchanged, now at +0x63)
    compact assistant area                the device pads records with 0xff runs; the GUI does not

and blocks are emitted with the e4-slot block first, because the file's unit walk depends on order
(v1 of this transform emitted the download's order and was rejected mk2vsc-49).

``to_upload_form(device, reference=None, timestamp=None)``:
  * with ``reference`` (a real GUI export of the SAME system) the compact assistant area is copied from it
    and the transform must reproduce the reference byte-for-byte per block except pointers and checksums;
    that is the self-test we ran, and ``tests/test_experimental.py`` re-runs it on the fixtures;
  * without a reference the compaction strips 0xff runs of 8 bytes or more from the assistant area and
    stamps ``timestamp`` (default: now) as the export/save times.

Two residual unknowns are documented rather than hidden: what BLOB12 means, and whether the 0xff-run
heuristic is the GUI's actual rule (it reproduces both records we hold: 1152 -> 1102, 704 -> 670).
"""
from __future__ import annotations

import difflib
import struct
import time
from typing import Dict, List, Optional, Tuple

from ..sections import RvmsFile, SECTION_DATA
from ..units import unit_blocks, UnitBlock, OFF_BLOB, OFF_SAVE_TS_DEVICE, ASSISTANT_FLAGS

BLOB12 = bytes.fromhex("010008004a3981804e93d70c")
HDR = len(SECTION_DATA) + 4          # name + next-pointer: bytes of a block that are not payload


class TransformRefused(RuntimeError):
    pass


def _strip_ff_runs(data: bytes, min_run: int = 8) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0xFF:
            j = i
            while j < len(data) and data[j] == 0xFF:
                j += 1
            if j - i >= min_run:
                i = j
                continue
        out.append(data[i])
        i += 1
    return bytes(out)


def _compact_with_reference(dev_area: bytes, ref_area: bytes) -> bytes:
    """Copy the reference's compact area wherever it differs from the device's padded area."""
    sm = difflib.SequenceMatcher(None, dev_area, ref_area, autojunk=False)
    out = bytearray()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out += dev_area[i1:i2]
        elif tag in ("replace", "insert"):
            out += ref_area[j1:j2]
    return bytes(out)


def to_upload_form(device: bytes, reference: Optional[bytes] = None, timestamp: Optional[int] = None) -> bytes:
    f = RvmsFile.parse(device)
    if not f.all_checksums_ok:
        raise TransformRefused("device file checksums invalid")
    units = unit_blocks(f)
    if any(u.is_upload_form for u in units):
        raise TransformRefused("input is already in upload form")
    if not all(u.assistant_flag in ASSISTANT_FLAGS for u in units):
        raise TransformRefused("this transform is only derived for blocks that carry an assistant")
    ref_by_slot: Dict[tuple, UnitBlock] = {}
    if reference is not None:
        fr = RvmsFile.parse(reference)
        ru = unit_blocks(fr)
        if not all(u.is_upload_form for u in ru):
            raise TransformRefused("reference must be a GUI export (upload form)")
        ref_by_slot = {u.slot: u for u in ru}
        if {u.serial for u in ru} != {u.serial for u in units}:
            raise TransformRefused("reference is for a different system")
    ts = int(time.time()) if timestamp is None else int(timestamp)

    # e4-slot block first (the order the GUI writes; the device's unit walk depends on it)
    order = sorted(units, key=lambda u: u.assistant_flag)
    payloads: List[bytes] = [s.payload for s in f.sections if not s.is_unit]
    for u in order:
        raw = u.raw
        ref = ref_by_slot.get(u.slot)
        nb = bytearray(raw[:OFF_BLOB])
        if ref is not None:
            nb += ref.raw[OFF_BLOB: OFF_BLOB + 16]                       # BLOB12 + export ts, verbatim
            nb += b"\x00" * 4
            nb += ref.raw[OFF_SAVE_TS_DEVICE + 10: OFF_SAVE_TS_DEVICE + 14]   # save ts, verbatim
        else:
            nb += BLOB12 + struct.pack("<I", ts)
            nb += b"\x00" * 4
            nb += struct.pack("<I", ts - 20)
        nb += raw[OFF_SAVE_TS_DEVICE + 4: u.assistant_area_offset]     # zeros, 0x0180, settings
        dev_area = u.assistant_area
        if ref is not None:
            area = _compact_with_reference(dev_area, ref.assistant_area)
        else:
            area = _compact_no_reference(dev_area)
        nb += area
        payloads.append(bytes(nb[HDR:]))            # drop name + pointer; rebuild re-adds them
    out = f.rebuild(payloads).to_bytes()
    chk = RvmsFile.parse(out)
    if not chk.all_checksums_ok or not all(u.is_upload_form for u in unit_blocks(chk)):
        raise TransformRefused("internal error: output does not parse as upload form")
    return out


def _compact_no_reference(area: bytes) -> bytes:
    """Strip padding from each record body and rewrite its length; strip padding from the tail.

    Records: ``f5 ff <subtype> <len> <body>``.  The device pads bodies with 0xff runs; the GUI stores the
    body compact and a correspondingly smaller length.  We only hold two records to check this against
    (1152 -> 1102, 704 -> 670); both reproduce.
    """
    out = bytearray()
    pos = 0
    while pos + 6 <= len(area) and area[pos: pos + 2] == b"\xf5\xff":
        subtype, length = struct.unpack_from("<HH", area, pos + 2)
        body = _strip_ff_runs(area[pos + 6: pos + 6 + length])
        out += b"\xf5\xff" + struct.pack("<HH", subtype, len(body)) + body
        pos += 6 + length
    # tail: device form is 0xff padding + `0e 00 8e 01 15 00 <4 slot bytes> ff 00 00`; the GUI writes
    # `ff <u16 free> 0a 00` + the same 10 trailer bytes + `00 00 00`, where free = 2812 - bytes used by the
    # compact records (observed on the installer's export and on the one transformed file the device accepted).
    tail = area[pos:]
    k = tail.find(b"\x0e\x00\x8e\x01\x15\x00")
    if k < 0 or len(tail) < k + 13:
        raise TransformRefused("device tail does not carry the expected 0e 00 8e 01 15 00 trailer")
    trailer10 = tail[k: k + 10]
    out += b"\xff" + struct.pack("<H", 2812 - len(out)) + b"\x0a\x00" + trailer10 + b"\x00\x00\x00"
    return bytes(out)


def compare_per_slot(a: bytes, b: bytes) -> Dict[tuple, List[int]]:
    """Differing block offsets per slot, ignoring the next-pointer bytes and the checksum.  Used by the
    self-test: transform(device, reference) must reproduce the reference with no remaining differences."""
    ua = {u.slot: u for u in unit_blocks(RvmsFile.parse(a))}
    ub = {u.slot: u for u in unit_blocks(RvmsFile.parse(b))}
    out = {}
    for slot in ua:
        x, y = ua[slot].raw, ub[slot].raw
        n = min(len(x), len(y))
        diffs = [i for i in range(n) if x[i] != y[i] and i not in (0x0F, 0x10) and i < n - 4]
        if len(x) != len(y):
            diffs.append(-abs(len(x) - len(y)))
        out[slot] = diffs
    return out
