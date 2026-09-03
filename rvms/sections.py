"""
Section-level parser and serializer for Victron VEConfigure ``.rvms`` files.

Observed file grammar (every file in the 84-file corpus, no exceptions)::

    file     := magic section*
    magic    := u16 name_len | "VEConfig setting section file"          (29 bytes, no pointer, no checksum)
    section  := u16 name_len | name | u32 next | payload | u32 checksum
    next     := absolute file offset of the NEXT section's u16 prefix; == file length for the last section
    checksum := 32-bit little-endian word sum over [section_start, checksum_start), mod 2**32.
                A trailing partial word (span not a multiple of 4) is zero-padded on the high side.

Sections seen, always in this order:

    Mk2vscInfo       payload: u32 (=1) | u16 len | "1.33"          -- format/tool version
    BareSettingInfo  payload: 0x0fb7 bytes, byte-identical across every file we hold (a template/schema)
    BareSettingData  one per inverter in the VE.Bus system (our systems are pairs -> two sections)

Notes on history, because earlier tooling used a different (equivalent) description:

* The first implementation summed ``block[0x02:field]`` where ``block`` began at the ``B`` of
  ``BareSettingData`` and added a "magic init constant" ``0x6142000F``.  That constant is simply the
  first word of the section read from its length prefix: ``0f 00 42 61`` -> LE ``0x6142000F``.
  There is no magic constant; the sum starts at the length prefix.
* The "``0f 00`` framing" that ended every block but the last is the *next section's* name-length
  prefix (15 = len("BareSettingData")).  It belongs to the next section, not to the block.
* The checksum applies to every section (Mk2vscInfo, BareSettingInfo, BareSettingData), not only the
  per-unit blocks.  All 107 files x all sections validate.

This module does not know what the payloads mean.  See ``units.py`` for the per-inverter block layout
and ``fields.py`` for the settings table.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional

MAGIC = b"VEConfig setting section file"
SECTION_MK2 = b"Mk2vscInfo"
SECTION_INFO = b"BareSettingInfo"
SECTION_DATA = b"BareSettingData"


class RvmsParseError(ValueError):
    """The bytes do not follow the observed section grammar."""


def sum32_le(data: bytes, start: int = 0, end: Optional[int] = None) -> int:
    """Sum ``data[start:end]`` as 32-bit little-endian words modulo 2**32.

    A trailing partial word is zero-padded on the high side.  This is the integrity function
    VEConfigure uses for every section trailer (validated on all 107 corpus files).
    """
    if end is None:
        end = len(data)
    total = 0
    i = start
    while i < end:
        w = 0
        for j in range(4):
            if i + j < end:
                w |= data[i + j] << (8 * j)
        total = (total + w) & 0xFFFFFFFF
        i += 4
    return total


@dataclass
class Section:
    """One ``u16 len | name | u32 next | payload | u32 checksum`` record.

    Offsets are absolute within the file the section was parsed from.  ``raw`` is the exact bytes
    ``[start, end)`` so that a parsed file can be re-emitted byte-for-byte.
    """

    start: int
    name: bytes
    next_ptr: int
    payload: bytes
    stored_checksum: int
    raw: bytes = field(repr=False)

    @property
    def name_start(self) -> int:
        """Offset of the first byte of the section name (the ``B`` in ``BareSettingData``)."""
        return self.start + 2

    @property
    def payload_start(self) -> int:
        return self.start + 2 + len(self.name) + 4

    @property
    def end(self) -> int:
        return self.start + len(self.raw)

    @property
    def checksum_offset(self) -> int:
        return self.end - 4

    @property
    def computed_checksum(self) -> int:
        return sum32_le(self.raw, 0, len(self.raw) - 4)

    @property
    def checksum_ok(self) -> bool:
        return self.computed_checksum == self.stored_checksum

    @property
    def is_unit(self) -> bool:
        return self.name == SECTION_DATA

    @staticmethod
    def build(name: bytes, next_ptr: int, payload: bytes, start: int) -> "Section":
        """Assemble a section with a freshly computed checksum."""
        head = struct.pack("<H", len(name)) + name + struct.pack("<I", next_ptr)
        body = head + payload
        ck = sum32_le(body)
        raw = body + struct.pack("<I", ck)
        return Section(start=start, name=name, next_ptr=next_ptr, payload=payload, stored_checksum=ck, raw=raw)


@dataclass
class RvmsFile:
    """A parsed ``.rvms``: the magic header plus an ordered list of sections."""

    magic_raw: bytes
    sections: List[Section]
    length: int

    # ------------------------------------------------------------------ parsing
    @classmethod
    def parse(cls, data: bytes) -> "RvmsFile":
        if len(data) < 2 + len(MAGIC):
            raise RvmsParseError("file too short to hold the magic header")
        n = struct.unpack_from("<H", data, 0)[0]
        if data[2 : 2 + n] != MAGIC:
            raise RvmsParseError(f"bad magic: {data[2:2+n]!r}")
        pos = 2 + n
        sections: List[Section] = []
        while pos < len(data):
            if pos + 2 > len(data):
                raise RvmsParseError(f"truncated section prefix at {pos:#x}")
            nlen = struct.unpack_from("<H", data, pos)[0]
            name = data[pos + 2 : pos + 2 + nlen]
            if nlen == 0 or nlen > 64 or not name.isalnum():
                raise RvmsParseError(f"implausible section name {name[:24]!r}... at {pos:#x} (pointer chain broken?)")
            ptr_at = pos + 2 + nlen
            if ptr_at + 4 > len(data):
                raise RvmsParseError(f"truncated next-pointer for {name!r} at {pos:#x}")
            nxt = struct.unpack_from("<I", data, ptr_at)[0]
            if nxt <= ptr_at + 4 + 4 or nxt > len(data):
                raise RvmsParseError(
                    f"section {name!r} at {pos:#x} has next-pointer {nxt:#x} outside [{ptr_at+8:#x}, {len(data):#x}]"
                )
            raw = data[pos:nxt]
            payload = raw[2 + nlen + 4 : -4]
            stored = struct.unpack_from("<I", raw, len(raw) - 4)[0]
            sections.append(Section(start=pos, name=name, next_ptr=nxt, payload=payload, stored_checksum=stored, raw=raw))
            pos = nxt
        return cls(magic_raw=data[: 2 + n], sections=sections, length=len(data))

    @classmethod
    def load(cls, path: str) -> "RvmsFile":
        with open(path, "rb") as fh:
            return cls.parse(fh.read())

    # ------------------------------------------------------------------ queries
    def section(self, name: bytes) -> Section:
        for s in self.sections:
            if s.name == name:
                return s
        raise KeyError(name)

    @property
    def unit_sections(self) -> List[Section]:
        return [s for s in self.sections if s.is_unit]

    @property
    def all_checksums_ok(self) -> bool:
        return all(s.checksum_ok for s in self.sections)

    def checksum_report(self) -> List[tuple]:
        """[(name, start, stored, computed, ok)] for every section."""
        return [(s.name.decode(), s.start, s.stored_checksum, s.computed_checksum, s.checksum_ok) for s in self.sections]

    # ------------------------------------------------------------------ serializing
    def to_bytes(self) -> bytes:
        """Re-emit exactly the bytes that were parsed (no recomputation)."""
        return self.magic_raw + b"".join(s.raw for s in self.sections)

    def rebuild(self, payloads: Optional[List[bytes]] = None) -> "RvmsFile":
        """Return a new file with pointers and checksums recomputed from (possibly replaced) payloads.

        ``payloads`` replaces the payload of each section positionally; ``None`` keeps them.  This is the
        only path that changes file length, so it is what a structure-changing edit must go through.
        """
        if payloads is None:
            payloads = [s.payload for s in self.sections]
        if len(payloads) != len(self.sections):
            raise ValueError("payload count must match section count")
        out: List[Section] = []
        pos = len(self.magic_raw)
        for s, p in zip(self.sections, payloads):
            size = 2 + len(s.name) + 4 + len(p) + 4
            nxt = pos + size
            out.append(Section.build(s.name, nxt, p, pos))
            pos = nxt
        return RvmsFile(magic_raw=self.magic_raw, sections=out, length=pos)

    def fixed(self) -> "RvmsFile":
        """Same content with every checksum recomputed (pointers untouched)."""
        return self.rebuild()


# ---------------------------------------------------------------------- forensic fallback
def scan_unit_blocks(data: bytes) -> List[tuple]:
    """Locate ``BareSettingData`` blocks by string search, ignoring the pointer chain.

    Returns ``[(name_start, end)]`` where ``end`` is the next block's name start or EOF.  This is the
    delimiting convention the first-generation tools used (a "block" runs from ``B`` to the next ``B``,
    so it *includes* the next section's 2-byte length prefix).  Use it only to inspect files whose pointer
    chain is broken; ``RvmsFile.parse`` is authoritative for well-formed files.
    """
    marks = []
    i = data.find(SECTION_DATA)
    while i >= 0:
        marks.append(i)
        i = data.find(SECTION_DATA, i + 1)
    return [(marks[k], marks[k + 1] if k + 1 < len(marks) else len(data)) for k in range(len(marks))]
