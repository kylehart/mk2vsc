"""
Self-check of the settings-array offset against the file's own schema.

The settings array is read at a fixed block offset (+0x59 device form, +0x63 upload form).  A file
from another firmware or tool build could put a different number of bytes before it, and fixed offsets
would then decode the wrong bytes as settings without any error.  The file carries its own defence:
``BareSettingInfo`` declares min and max for every index, so the true offset is the one at which the
u16 values fall inside their own ranges.  ``score`` counts that; ``find_offset`` tries candidates.

Bitfield registers (whose "max" is a mask) and unused entries are excluded from the count, so a
perfect score on our corpus is 138 of 138 scorable settings (190 minus 47 unused minus 5 bitfields).  A wrong offset scores far lower: shifting
by two bytes turns voltages into flag words and durations into capacities.

Method after talas9/rvsc-tools, which locates the array this way on every file rather than assuming.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .schema import SettingInfo
from .units import UnitBlock, N_SETTINGS, OFF_SETTINGS_DEVICE, UPLOAD_SHIFT

BITFIELD_IDS = {0, 1, 60, 61, 77, 78, 82}
N_SCORED = 190            # 190 and 191 are 0..65535 in the schema and score nothing


@dataclass
class Alignment:
    expected: int          # the offset the layout model predicts for this block
    best: int              # the best-scoring candidate
    score: int             # in-range count at the best candidate
    total: int             # scorable settings
    expected_score: int    # in-range count at the expected offset

    @property
    def ok(self) -> bool:
        return self.best == self.expected and self.score == self.total

    @property
    def summary(self) -> str:
        if self.ok:
            return f"alignment OK (+0x{self.expected:03x}, {self.score}/{self.total} in range)"
        return (f"ALIGNMENT SUSPECT: expected +0x{self.expected:03x} scores {self.expected_score}/{self.total}, "
                f"best +0x{self.best:03x} scores {self.score}/{self.total}")


def score(raw: bytes, offset: int, schema: List[SettingInfo]) -> Tuple[int, int]:
    """(in_range, scorable) for a settings array assumed to start at ``offset`` within ``raw``."""
    hit = tot = 0
    for r in schema[:N_SCORED]:
        if r.unused or r.id in BITFIELD_IDS:
            continue
        o = offset + 2 * r.id
        if o + 2 > len(raw):
            return hit, tot + 1
        tot += 1
        if r.in_range(struct.unpack_from("<H", raw, o)[0]):
            hit += 1
    return hit, tot


def find_offset(raw: bytes, schema: List[SettingInfo], candidates: Optional[range] = None) -> Tuple[int, int, int]:
    """(best_offset, best_score, total) over the candidate offsets (default: every offset 0x40..0x80)."""
    best = (-1, -1, 0)
    for off in (candidates or range(0x40, 0x81)):
        h, t = score(raw, off, schema)
        if h > best[1]:
            best = (off, h, t)
    return best


def check(u: UnitBlock, schema: List[SettingInfo]) -> Alignment:
    expected = u.settings_offset
    eh, tot = score(u.raw, expected, schema)
    b_off, b_score, _ = find_offset(u.raw, schema)
    return Alignment(expected=expected, best=b_off, score=b_score, total=tot, expected_score=eh)
