"""
Per-inverter block model: the layout of a ``BareSettingData`` section.

All offsets in this module are **relative to the section's name start** (the ``B`` of
``BareSettingData``), because that is how every prior note, tool, and change record in this project
addressed them.  ``Section.name_start`` converts to an absolute file offset.

Layout of a device-form block (what VRM's Remote VEConfigure *download* produces)::

    +0x00  "BareSettingData"                       15 bytes, section name
    +0x0f  u32 next-section pointer                (see sections.py)
    +0x13  u32  = 3                                unknown; constant 3 in every corpus block
    +0x17  u32  per-unit constant                  bytes +0x18..0x19 track the serial's date code
                                                   (hardware/production batch, NOT firmware)
    +0x1b  u32  firmware word                      low 24 bits = the seven-digit VE.Bus firmware number
                                                   (2729560 == "v560" in VRM on the corpus); the high byte is
                                                   0 on every corpus block and is reported separately
                                                   (``firmware_word_high_byte``, docs/FORMAT.md 3.3)
    +0x1f  ...  unknown header bytes
    +0x35  u8   phase byte       00 / 86 on a split-phase pair; 00 / 04 / 08 on three-phase files (L1/L2/L3);
                                 00 on a single unit
    +0x36  u8   assistant flag   high nibble f = no assistant, e = assistant present;
                                 low nibble = a phase/role code (4|5 split-phase pair, 8|9|a three-phase, 0 single)
    +0x37  u8   unit index       0 / 1 on a pair; 0..n-1 on three-phase files; 0 on a single unit
    +0x3a  ASCII serial number  "HQ..."            11 characters, zero padded
    +0x45  10 zero bytes                            (upload form: a 16-byte blob + 4 zeros instead; +10 shift)
    +0x4f  u32 unix timestamp of file generation    new on every download; NOT an acceptance gate (docs/FORMAT.md 3.2)
    +0x53  u32 = 0
    +0x57  u16 = 0x0180                             unknown, constant
    +0x59  u16[192] VE.Bus settings array           setting ID n at +0x59 + 2n   (see fields.py);
                                                    190/191 are the grid-code LOM words (ff ff / f5 ff ...)
    +0x1d9 assistant area                           u16 length | body | tail;  bare: 00 00 ff 00 0b
    ...    u32 checksum                              last 4 bytes of the section

Upload form (what the VEConfigure/System Configurator GUI *writes* for upload) inserts 16 bytes at
+0x45 (12 constant bytes + a u32 export timestamp) followed by 4 zero bytes, in place of the 10 zeros,
so every later offset shifts by +10: settings start at +0x63 and the save timestamp sits at +0x59.
Device downloads never carry that blob (zeros).  The GUI also writes assistant records in a compact form
(no 0xff padding runs); the device stores them padded.  See docs/FORMAT.md.
"""
from __future__ import annotations

import datetime as _dt
import re
import struct
from dataclasses import dataclass
from typing import Dict, List, Optional

from .sections import RvmsFile, Section, SECTION_DATA, SECTION_INFO, SectionTooShort
from .schema import check_payload as _check_schema_payload

SERIAL_RE = re.compile(rb"HQ[0-9A-Z]{8,12}")

OFF_NEXT_PTR = 0x0F
OFF_HEADER_CONST = 0x13
OFF_UNIT_CONST = 0x17
OFF_FIRMWARE = 0x1B
OFF_SLOT_A = 0x35        # phase byte
OFF_ASSISTANT_FLAG = 0x36
OFF_SLOT_B = 0x37        # unit index
FIRMWARE_MASK = 0xFFFFFF  # the seven-digit firmware number never needs bits 24..31 (9,999,999 < 2**24)
OFF_SERIAL = 0x3A
OFF_BLOB = 0x45          # 10 zero bytes (device form) or 16-byte blob + 4 zeros (upload form)
OFF_SAVE_TS_DEVICE = 0x4F
OFF_SETTINGS_DEVICE = 0x59
UPLOAD_SHIFT = 10
N_SETTINGS = 192          # settings 0..191 precede the assistant area; the schema has 192 records too
PREFIX_LEN = 15 + 4       # name + next pointer: the bytes of ``raw`` before the payload
SETTINGS_END_DEVICE = OFF_SETTINGS_DEVICE + 2 * N_SETTINGS          # 0x1d9: first byte after the settings array
MIN_PAYLOAD_DEVICE = SETTINGS_END_DEVICE - PREFIX_LEN               # 454: payload bytes the fixed layout reads

ASSISTANT_FLAGS = {0xE4, 0xE5}   # the split-phase pair values the writer-side tools (assistant, upload_form) handle
BARE_FLAGS = {0xF4, 0xF5}

# Phase byte (+0x35) labels.  Observed: 00 on every single-unit block; 00 / 86 on the two blocks of a split-phase
# pair (corpus); 00 / 04 / 08 on three-phase files, cycling with the unit index.  Inferred: the L1/L2/L3 reading.
PHASE_LABELS = {0x00: "L1", 0x04: "L2", 0x08: "L3", 0x86: "L2 (split-phase)"}

# Byte offsets (device form) that change on a re-save with NO setting change.  Never treat as settings.
VOLATILE_DEVICE = {OFF_NEXT_PTR, OFF_NEXT_PTR + 1, OFF_SAVE_TS_DEVICE, OFF_SAVE_TS_DEVICE + 1,
                   OFF_SAVE_TS_DEVICE + 2, OFF_SAVE_TS_DEVICE + 3}


@dataclass
class UnitBlock:
    """A view over one ``BareSettingData`` section with named accessors."""

    section: Section
    index: int  # position in the file (0-based); NOT stable across downloads, use serial

    def __post_init__(self):
        # Every fixed-offset read below ends at the settings array; refuse a block that cannot hold it, by name,
        # instead of failing inside ``struct`` (see docs/ERRORS.md, SectionTooShort).
        need = MIN_PAYLOAD_DEVICE + self.shift
        have = len(self.section.payload)
        if have < need:
            raise SectionTooShort(SECTION_DATA.decode() + f" (inverter block {self.index})", have, need,
                                  f"the {N_SETTINGS}-entry settings array at +0x{self.settings_offset:x} from the name start, "
                                  f"then the assistant area and the checksum")

    # ------------------------------------------------------------- raw helpers
    @property
    def raw(self) -> bytes:
        """Bytes from the name start (``B``) to the end of the section (checksum inclusive)."""
        return self.section.raw[2:]

    def u8(self, off: int) -> int:
        return self.raw[off]

    def u16(self, off: int) -> int:
        return struct.unpack_from("<H", self.raw, off)[0]

    def u32(self, off: int) -> int:
        return struct.unpack_from("<I", self.raw, off)[0]

    @property
    def length(self) -> int:
        """Length in the first-generation convention (``B`` to next ``B``): section minus its prefix
        plus the following prefix.  Bare pairs read 0x1e4 / 0x1e2 in this convention."""
        return len(self.raw) + 2 if not self.is_last else len(self.raw)

    is_last: bool = False

    # ------------------------------------------------------------- identity
    @property
    def serial(self) -> str:
        m = SERIAL_RE.search(self.raw[OFF_SERIAL: OFF_SERIAL + 16])
        if not m:
            m = SERIAL_RE.search(self.raw[: 0x80])
        return m.group().decode() if m else "?"

    @property
    def firmware_word(self) -> int:
        """The u32 at +0x1b as stored."""
        return self.u32(OFF_FIRMWARE)

    @property
    def firmware_version(self) -> int:
        """The seven-digit VE.Bus firmware number: the low 24 bits of the firmware word (``FIRMWARE_MASK``)."""
        return self.firmware_word & FIRMWARE_MASK

    @property
    def firmware_word_high_byte(self) -> int:
        """Bits 24..31 of the firmware word: 0 on every corpus block; 0xc7 on one GUI-saved three-unit file seen
        outside the corpus (docs/FORMAT.md 3.3).  Not part of the firmware number."""
        return self.firmware_word >> 24

    @property
    def unit_constant(self) -> int:
        return self.u32(OFF_UNIT_CONST)

    @property
    def assistant_flag(self) -> int:
        return self.u8(OFF_ASSISTANT_FLAG)

    @property
    def has_assistant_flag(self) -> bool:
        """High nibble ``e`` of the flag byte.  Observed: ``e`` on every block that carries assistant records and
        ``f`` on every block without, across the corpus (e4/e5, f4/f5) and the single-unit, parallel and
        three-phase files run through tools/validate_dir.py (e0, f0, e8, e9, ea)."""
        return (self.assistant_flag >> 4) == 0xE

    @property
    def slot(self) -> tuple:
        return (self.u8(OFF_SLOT_A), self.u8(OFF_SLOT_B))

    @property
    def phase_byte(self) -> int:
        return self.u8(OFF_SLOT_A)

    @property
    def unit_index(self) -> int:
        return self.u8(OFF_SLOT_B)

    @property
    def phase_label(self) -> str:
        return PHASE_LABELS.get(self.phase_byte, f"?0x{self.phase_byte:02x}")

    @property
    def phase_summary(self) -> str:
        """``L2, unit 1`` style text for reports: the phase label and the unit index, from +0x35 and +0x37."""
        return f"{self.phase_label}, unit {self.unit_index}"

    # ------------------------------------------------------------- form
    @property
    def is_upload_form(self) -> bool:
        """True when the 16-byte GUI export blob is present at +0x45 (VEConfigure/GUI output)."""
        return any(self.raw[OFF_BLOB: OFF_BLOB + 10])

    @property
    def shift(self) -> int:
        return UPLOAD_SHIFT if self.is_upload_form else 0

    @property
    def settings_offset(self) -> int:
        return OFF_SETTINGS_DEVICE + self.shift

    @property
    def save_timestamp(self) -> int:
        return self.u32(OFF_SAVE_TS_DEVICE + self.shift)

    @property
    def save_datetime(self) -> Optional[_dt.datetime]:
        t = self.save_timestamp
        if 946684800 < t < 4102444800:
            return _dt.datetime.fromtimestamp(t, _dt.timezone.utc)
        return None

    @property
    def export_timestamp(self) -> Optional[int]:
        """Upload-form only: the u32 at +0x51 (last 4 bytes of the 16-byte blob)."""
        if not self.is_upload_form:
            return None
        return self.u32(OFF_BLOB + 12)

    # ------------------------------------------------------------- settings array
    def setting_offset(self, setting_id: int) -> int:
        if not 0 <= setting_id < N_SETTINGS:
            raise IndexError(f"setting id {setting_id} outside 0..{N_SETTINGS-1}")
        return self.settings_offset + 2 * setting_id

    def setting(self, setting_id: int) -> int:
        return self.u16(self.setting_offset(setting_id))

    def settings(self) -> List[int]:
        base = self.settings_offset
        return list(struct.unpack_from(f"<{N_SETTINGS}H", self.raw, base))

    @property
    def assistant_area_offset(self) -> int:
        return self.settings_offset + 2 * N_SETTINGS

    @property
    def assistant_area(self) -> bytes:
        """Bytes after the settings array up to (excluding) the checksum."""
        return self.raw[self.assistant_area_offset: len(self.raw) - 4]

    # ------------------------------------------------------------- summary
    def summary(self) -> Dict:
        return {
            "serial": self.serial,
            "index": self.index,
            "length": self.length,
            "form": "upload" if self.is_upload_form else "device",
            "assistant_flag": f"{self.assistant_flag:02x}",
            "assistant_present": self.has_assistant_flag,
            "slot": self.slot,
            "phase": self.phase_label,
            "unit_index": self.unit_index,
            "firmware": self.firmware_version,
            "firmware_word_high_byte": self.firmware_word_high_byte,
            "unit_constant": f"{self.unit_constant:08x}",
            "save_time_utc": self.save_datetime.isoformat() if self.save_datetime else None,
            "assistant_area_bytes": len(self.assistant_area),
            "checksum_ok": self.section.checksum_ok,
        }


def check_layout(f: RvmsFile) -> None:
    """Raise ``SectionTooShort`` if any section that parsed is too short for the layout mk2vsc reads:
    the ``BareSettingInfo`` schema (192 records) and every ``BareSettingData`` block (the settings array).
    A file with no ``BareSettingInfo`` at all is left to the callers' existing no-schema handling."""
    for s in f.sections:
        if s.name == SECTION_INFO:
            _check_schema_payload(s.payload)
    unit_blocks(f)


def unit_blocks(f: RvmsFile) -> List[UnitBlock]:
    units = [s for s in f.sections if s.name == SECTION_DATA]
    out = []
    for i, s in enumerate(units):
        out.append(UnitBlock(section=s, index=i, is_last=(s is f.sections[-1])))
    return out


def units_by_serial(f: RvmsFile) -> Dict[str, UnitBlock]:
    """Blocks keyed by inverter serial.  Block ORDER is not stable across downloads of the same
    system (proven 2026-07-24); always compare by serial."""
    d: Dict[str, UnitBlock] = {}
    for u in unit_blocks(f):
        if u.serial in d:
            raise ValueError(f"duplicate serial {u.serial} in file")
        d[u.serial] = u
    return d
