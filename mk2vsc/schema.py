"""
The device's own settings schema, read from the ``BareSettingInfo`` section.

``BareSettingInfo`` (4001 bytes, identical in every file we hold) starts with an 11-byte header
(``04 00 00 00`` | u32 firmware version | ``02 80 07``) followed by one 10-byte record per setting::

    record := i16 scale | i16 offset | u16 default | u16 min | u16 max

192 records (settings 0 to 191; 190 and 191 carry only a default).  The engineering value of a raw
u16 is::

    value = (raw + offset) / |scale|     if scale < 0      (divisor)
    value = (raw + offset) * scale       if scale > 0      (multiplier, e.g. 15-minute units)
    value = raw                          if scale == 0     (unused setting)

Checks that hold on every corpus block: absorption/float (scale -100, 48.00 to 64.00 V, defaults 57.60
and 55.20), charge current (0 to 35 A on this model), output voltage (95 to 128 V), AC input limit
(scale -10, 1.0 to 100.0 A), charge efficiency (scale -256, offset +1: 255 -> 1.000), SoC fields
(scale -2), the Virtual Switch durations (offset -1, seconds or minutes), output frequency as a period
(setting 62: 41667/2500 ms = 16.667 ms = 60 Hz, range 45 to 65 Hz), and the flags register whose "max"
is the mask of settable bits.  189 of the 190 bounded settings (0 to 189) in the corpus fall inside their own [min, max]; the
exception is that flags mask.

The 2070 bytes after the records (a per-setting attribute byte table and an offset-indexed set of
variable-length ``f5 ff 3e 0f`` records) are not decoded; see issue #6.

TODO (other firmware): ``HEADER_LEN``, ``RECORD_LEN`` and ``N_RECORDS`` are the values Observed on the one
firmware in the corpus (2729560) and are not generalised.  A payload shorter than they imply is refused as
``SectionTooShort`` with the observed length and the record count it would hold.  Evidence that other
firmware differs: talas9/rvsc-tools (MIT) reads its reference file, a 4562-byte single-unit save from a
MultiPlus 24/1200 on firmware 2667558 with VEConfigure 1.33, by searching the ``BareSettingInfo`` header
length (``info_header_search_range``) and treating ``BareSettingInfo`` as a master table of which
``BareSettingData`` covers a window (its rvsc.py, ``find_alignment``; its FORMAT.md section 2).  We hold no
such file; generalising the header or record count waits for one (issues #14 single-unit .rvsc, #16 other
firmware, #36 schema signature per firmware; CONTRIBUTING.md, "Files from hardware we do not have").
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List, Optional

from .sections import RvmsFile, SECTION_INFO, SectionTooShort

HEADER_LEN = 11
RECORD_LEN = 10
N_RECORDS = 192
SCHEMA_LEN = HEADER_LEN + N_RECORDS * RECORD_LEN     # 1931: the payload length the 192-record schema needs


@dataclass(frozen=True)
class SettingInfo:
    id: int
    scale: int      # signed: <0 divisor, >0 multiplier, 0 unused
    offset: int     # signed, added to the raw value before scaling
    default: int
    min: int
    max: int

    def decode(self, raw: int) -> float:
        if self.scale < 0:
            return (raw + self.offset) / -self.scale
        if self.scale > 0:
            return (raw + self.offset) * self.scale
        return raw

    def encode(self, value: float) -> int:
        if self.scale < 0:
            raw = round(value * -self.scale) - self.offset
        elif self.scale > 0:
            raw = round(value / self.scale) - self.offset
        else:
            raw = int(value)
        return int(raw)

    def in_range(self, raw: int) -> bool:
        return self.min <= raw <= self.max

    @property
    def unused(self) -> bool:
        return self.scale == 0 and self.max == 0


def check_payload(info_payload: bytes) -> None:
    """Raise ``SectionTooShort`` unless the payload holds the 11-byte header and 192 records."""
    if len(info_payload) < SCHEMA_LEN:
        implied = max(0, (len(info_payload) - HEADER_LEN) // RECORD_LEN)
        raise SectionTooShort(SECTION_INFO.decode(), len(info_payload), SCHEMA_LEN,
                              f"room for {implied} whole {RECORD_LEN}-byte records after the {HEADER_LEN}-byte header; "
                              f"the schema mk2vsc reads has {N_RECORDS}")


def parse_schema(info_payload: bytes) -> List[SettingInfo]:
    check_payload(info_payload)
    out = []
    for n in range(N_RECORDS):
        o = HEADER_LEN + RECORD_LEN * n
        scale, offset, dflt, mn, mx = struct.unpack_from("<hhHHH", info_payload, o)
        out.append(SettingInfo(n, scale, offset, dflt, mn, mx))
    return out


def schema_of(f: RvmsFile) -> List[SettingInfo]:
    return parse_schema(f.section(SECTION_INFO).payload)


def firmware_of_schema(info_payload: bytes) -> int:
    return struct.unpack_from("<I", info_payload, 4)[0]


NOMINALS = (12, 24, 48)


def nominal_voltage(schema: List[SettingInfo]) -> int:
    """The system's nominal battery voltage, read from the file's own schema.

    The absorption record's minimum is the nominal voltage on every Victron model we know of (48.00 V
    on the 48 V MultiPlus in the corpus; 24.00 V on talas9's 24 V unit).  Returns 12, 24 or 48, or raises
    ``ValueError`` when the minimum is not within 10 % of one of those, so a caller never scales a bound
    by a guess.  Observed on the corpus: 48 on every file.  Inferred: 24 and 12 from the schema convention.
    """
    from .fields import BY_NAME
    r = schema[BY_NAME["absorption_V"].id]
    if r.scale == 0:
        raise ValueError("schema record 2 (absorption) is unused; cannot infer the nominal voltage")
    v = r.decode(r.min)
    for nom in NOMINALS:
        if abs(v - nom) <= nom * 0.10:
            return nom
    raise ValueError(f"absorption minimum {v:g} V is not near a Victron nominal (12/24/48 V); cannot infer the nominal voltage")
