"""
READ-ONLY parsing of the assistant area that follows the settings array in a unit block.

What we can say with evidence (docs/ASSISTANTS.md has the full story):

* Bare block (no assistant): the area is the 9 bytes ``ff ff ff ff 00 00 ff 00 0b`` (device form) --
  i.e. an empty record header (``ff ff`` marker, ``ff ff`` subtype, length ``00 00``) plus 3 trailer bytes.
* Block with the ESS assistant installed by the GUI: one or more records framed
  ``f5 ff <subtype u16> <len u16> <body>``; body lengths 704 and 1152 in every working install we hold
  (one per inverter of the pair; the two bodies differ from each other, and are byte-identical across
  systems except for a single primary/secondary flag byte).  The device pads records with ``0xff`` runs
  and appends trailer bytes; the GUI's upload form writes the same records compact.
* Stub: after VEConfigure accepted one of our transplanted files it wrote a 64-byte empty container
  ``40 00 a7 fe 00 00 57 01`` + ``0xff`` filler + ``c0 0a`` on both inverters and discarded our payload.
  Its presence in a download is the signature of a failed by-file assistant install.

We do NOT understand the record body.  It looks like a compiled program (entropy ~6.2 bits/byte,
recurring 2-3 byte opcodes, embedded parameter values such as 48.00 V and 10 %).  This module reports
structure; it does not author it.
"""
from __future__ import annotations

import struct
from typing import Dict, List

from .units import UnitBlock

RECORD_MARK = b"\xf5\xff"
EMPTY_MARK = b"\xff\xff"
CONTAINER_SIG = b"\xa7\xfe\x00\x00\x57\x01"
STUB_MAGIC = b"\x40\x00" + CONTAINER_SIG     # len 64 + signature, as it appears after the ff ff ff ff header


def parse_records(area: bytes):
    """Walk ``marker(2) subtype(2) len(2) body`` records from the start of the area.

    Returns (records, tail_offset).  Walking stops at the first byte pair that is not a known marker.
    """
    records: List[Dict] = []
    pos = 0
    while pos + 6 <= len(area) and area[pos: pos + 2] in (EMPTY_MARK, RECORD_MARK):
        marker = area[pos: pos + 2]
        subtype, length = struct.unpack_from("<HH", area, pos + 2)
        body = area[pos + 6: pos + 6 + length]
        records.append({"offset": pos, "marker": marker.hex(), "subtype": f"{subtype:04x}", "length": length,
                        "body_sha8": _sha8(body) if length else "", "nonpad_bytes": sum(1 for b in body if b != 0xFF),
                        "container_signature": body.startswith(CONTAINER_SIG),
                        "truncated": len(body) < length})
        pos += 6 + length
    return records, pos


def parse_assistant_area(u: UnitBlock) -> Dict:
    """Describe the assistant area of a unit block.

    Uniform model (every block in the corpus fits it)::

        area := record* tail
        record := marker(2) subtype(2) len(2) body[len]
        marker  ff ff  -> empty slot / container.  Bare blocks: len 0.  Two June-2026 files from an older
                          tool build: len 6, body a7 fe 00 00 57 01.  Stub written by VEConfigure after it
                          discarded a transplanted assistant: len 64, same signature + 0xff filler.
                f5 ff  -> assistant record.  GUI-installed ESS: one 704-byte and one 1152-byte record per
                          system (one on each inverter), subtype 0101 / 0001.
        tail   := padding(0xff)* | ff | u16 free
                  On bare, container and stub blocks free == 2816 - bytes used; see docs/FORMAT.md for ESS.

    A ``f5 ff`` header with len 0 where ``ff ff`` is expected is residue seen on downloads taken after a
    rejected or rolled-back assistant upload; functionally bare.
    """
    area = u.assistant_area
    records, tail_off = parse_records(area)
    tail = area[tail_off:]
    out: Dict = {"bytes": len(area), "records": records, "tail_bytes": len(tail), "tail_hex": tail[-8:].hex(" "),
                 "stub": False, "kind": "unknown", "summary": ""}
    if len(tail) >= 3 and tail[-3] == 0xFF:
        out["free"] = struct.unpack_from("<H", tail, len(tail) - 2)[0]
        out["used"] = tail_off
        out["free_plus_used"] = out["free"] + tail_off
    if any(r["truncated"] for r in records):
        out["kind"] = "malformed"
        out["summary"] = "record length exceeds the area (malformed)"
        return out
    real = [r for r in records if r["marker"] == "f5ff" and r["length"] > 0]
    containers = [r for r in records if r["marker"] == "ffff" and r["length"] > 0]
    if any(r["length"] >= 64 and r["container_signature"] for r in containers):
        out["kind"], out["stub"] = "stub", True
        out["summary"] = "EMPTY STUB container (signature of a failed by-file install)"
    elif real:
        out["kind"] = "records"
        out["summary"] = "assistant records: " + ", ".join(f"{r['length']}B/{r['subtype']}" for r in real)
    elif containers:
        out["kind"] = "container"
        out["summary"] = f"empty {containers[0]['length']}-byte container (no program)"
    elif records:
        out["kind"] = "none"
        out["summary"] = "no assistant" + (" (empty record residue)" if records[0]["marker"] == "f5ff" else "")
    else:
        out["summary"] = f"{len(area)} unrecognised bytes"
    return out


def _sha8(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()[:8]
