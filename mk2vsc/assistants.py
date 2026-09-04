"""
READ-ONLY parsing of the assistant area that follows the settings array in a unit block.

The area starts right after setting 191 (+0x1d9 device form, +0x1e3 upload form) and is one record::

    area := u16 length | body[length] | tail

* Bare block (no assistant): length 0, then the 3 trailer bytes ``ff 00 0b`` (free-space counter 2816).
* GUI-installed ESS: length 704 or 1152 (one per inverter of the pair, by role), then a 72-byte tail.
  The two bodies differ from each other and are byte-identical across systems except for a single
  primary/secondary flag byte.  The device pads the body with ``0xff`` runs; the GUI's upload form
  writes it compact (670 / 1102).
* Container: length 6, body ``a7 fe 00 00 57 01`` (two files from an older tool build).
* Stub: length 64, the same signature + ``0xff`` filler.  VEConfigure wrote this on both inverters after
  it accepted one of our transplanted files and discarded the payload; its presence in a download is the
  signature of a failed by-file assistant install.

The four bytes before the length (``ff ff ff ff`` bare, ``f5 ff 01 01`` on ESS blocks) are VE.Bus settings
190 and 191, the grid-code / loss-of-mains words; see ``grid_code_words`` and docs/FIELDS.md.

We do NOT understand the record body.  It looks like a compiled program (entropy ~6.2 bits/byte,
recurring 2-3 byte opcodes, embedded parameter values such as 48.00 V and 10 %).  This module reports
structure; it does not author it (`mk2vsc.assistant` removes records and reinstalls a system's own earlier ones).
"""
from __future__ import annotations

import struct
from typing import Dict, List

from .units import UnitBlock

CONTAINER_SIG = b"\xa7\xfe\x00\x00\x57\x01"
STUB_MAGIC = b"\x40\x00" + CONTAINER_SIG     # len 64 + signature, as it appears in the area
BUDGET = 2816                                # free-space counter + body length on bare/container/stub blocks


def parse_records(area: bytes):
    """Read the ``u16 length | body`` record at the start of the area.

    Returns (records, tail_offset).  ``records`` is a one-element list (or empty when the area is shorter
    than a length word) so callers can treat the area uniformly.
    """
    records: List[Dict] = []
    if len(area) < 2:
        return records, 0
    length = struct.unpack_from("<H", area, 0)[0]
    body = area[2: 2 + length]
    records.append({"offset": 0, "length": length,
                    "body_sha8": _sha8(body) if length else "", "nonpad_bytes": sum(1 for b in body if b != 0xFF),
                    "container_signature": body.startswith(CONTAINER_SIG),
                    "truncated": len(body) < length})
    return records, 2 + length


def parse_assistant_area(u: UnitBlock) -> Dict:
    """Describe the assistant area of a unit block (see the module docstring for the model)."""
    area = u.assistant_area
    records, tail_off = parse_records(area)
    tail = area[tail_off:]
    out: Dict = {"bytes": len(area), "records": records, "tail_bytes": len(tail), "tail_hex": tail[-8:].hex(" "),
                 "stub": False, "kind": "unknown", "summary": ""}
    if len(tail) >= 3 and tail[-3] == 0xFF:
        out["free"] = struct.unpack_from("<H", tail, len(tail) - 2)[0]
        out["used"] = records[0]["length"] if records else 0
        out["free_plus_used"] = out["free"] + out["used"]
    if any(r["truncated"] for r in records):
        out["kind"] = "malformed"
        out["summary"] = "record length exceeds the area (malformed)"
        return out
    rec = records[0] if records else None
    if rec is None:
        out["summary"] = f"{len(area)} unrecognised bytes"
    elif rec["length"] >= 64 and rec["container_signature"]:
        out["kind"], out["stub"] = "stub", True
        out["summary"] = "EMPTY STUB container (signature of a failed by-file install)"
    elif rec["length"] > 0 and rec["container_signature"]:
        out["kind"] = "container"
        out["summary"] = f"empty {rec['length']}-byte container (no program)"
    elif rec["length"] > 0:
        out["kind"] = "records"
        out["summary"] = f"assistant record: {rec['length']}B"
    else:
        out["kind"] = "none"
        out["summary"] = "no assistant"
    return out


def grid_code_words(u: UnitBlock) -> Dict:
    """Settings 81, 128, 190 and 191: the grid-code words, with the state the corpus supports.

    state: ``never`` (81 = 0 and all three words 0xffff: no grid code was ever applied), ``set`` (81 = 1;
    the words are populated and 128/191 follow the inverter's role in the pair), ``residual`` (81 = 0 but at
    least one word is not 0xffff: a grid code was applied and later removed; the firmware keeps some words).
    Which loss-of-mains mode a value encodes is documented for a single bench unit (xcellsior FINDINGS 7.4)
    and is not asserted here.
    """
    s81, s128, s190, s191 = (u.setting(i) for i in (81, 128, 190, 191))
    words = f"128={s128:#06x} 190={s190:#06x} 191={s191:#06x}"
    if s81 == 0 and s128 == 0xFFFF and s190 == 0xFFFF and s191 == 0xFFFF:
        state, summary = "never", "no grid code"
    elif s81 == 0:
        state, summary = "residual", f"no grid code, words residual ({words})"
    else:
        state, summary = "set", f"grid code {s81} ({words})"
        if s128 != s191:
            summary += "; 128 != 191, not seen on any GUI-authored download"
    return {"grid_code": s81, "w128": s128, "w190": s190, "w191": s191, "state": state, "summary": summary,
            "words_agree": s128 == s191}


def _sha8(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()[:8]
