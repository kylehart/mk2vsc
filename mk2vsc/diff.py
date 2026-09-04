"""
Compare two ``.rvms`` files **by inverter serial** and classify every differing byte.

Why by serial: the two blocks of a parallel pair swap file position between downloads of the same
system.  A naive byte diff of two consecutive downloads shows ~44 differences; compared by serial it is
exactly 6 bookkeeping bytes per block (next-pointer, save timestamp, checksum).  That distinction is
the basis of change verification: after an upload, the re-download must differ from what you uploaded
*only* in bookkeeping.

Classification of a differing block byte:

    bookkeeping   next-pointer (+0x0f..0x10), save timestamp (+0x4f..0x52 device form), checksum trailer
    setting       inside the settings array -> reported as (id, name, old, new)
    header        other bytes before the settings array (identity, flags, form blob)
    assistant     bytes in the assistant area
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .sections import RvmsFile
from .units import units_by_serial, UnitBlock, OFF_NEXT_PTR
from .fields import BY_ID


@dataclass
class UnitDiff:
    serial: str
    length_a: int          # raw section length (name start .. checksum), position independent
    length_b: int
    form_a: str
    form_b: str
    bookkeeping: List[int] = field(default_factory=list)
    settings: List[Dict] = field(default_factory=list)
    header: List[Dict] = field(default_factory=list)
    assistant: int = 0
    note: str = ""

    @property
    def only_bookkeeping(self) -> bool:
        same_len = self.length_a == self.length_b or self.form_a != self.form_b
        return not self.settings and not self.header and self.assistant == 0 and same_len


@dataclass
class FileDiff:
    identical: bool
    length_a: int
    length_b: int
    prologue_identical: bool
    only_in_a: List[str]
    only_in_b: List[str]
    units: List[UnitDiff]

    @property
    def only_bookkeeping(self) -> bool:
        return (self.prologue_identical and not self.only_in_a and not self.only_in_b
                and all(u.only_bookkeeping for u in self.units))

    def as_dict(self) -> Dict:
        return {
            "identical": self.identical, "only_bookkeeping": self.only_bookkeeping,
            "length": [self.length_a, self.length_b], "prologue_identical": self.prologue_identical,
            "only_in_a": self.only_in_a, "only_in_b": self.only_in_b,
            "units": [{"serial": u.serial, "length": [u.length_a, u.length_b], "form": [u.form_a, u.form_b],
                       "bookkeeping_bytes": [f"+0x{o:03x}" for o in u.bookkeeping],
                       "settings": u.settings, "header": u.header, "assistant_bytes_differ": u.assistant,
                       "note": u.note} for u in self.units],
        }


def _classify(a: UnitBlock, b: UnitBlock) -> UnitDiff:
    d = UnitDiff(a.serial, len(a.raw), len(b.raw), "upload" if a.is_upload_form else "device",
                 "upload" if b.is_upload_form else "device")
    ra, rb = a.raw, b.raw
    cross_form = a.is_upload_form != b.is_upload_form
    if cross_form:
        d.note = ("different forms (device vs upload): offsets shift by 10 after +0x45 and the GUI writes compact "
                  "assistant records, so lengths differ by form; settings compared by id")
    elif len(ra) != len(rb):
        d.note = "block length differs (assistant area changed)"
    # settings compared by id regardless of form
    sa, sb = a.settings(), b.settings()
    for sid, (x, y) in enumerate(zip(sa, sb)):
        if x != y:
            f = BY_ID.get(sid)
            d.settings.append({"id": sid, "name": f.name if f else None, "old_raw": x, "new_raw": y,
                               "old": f.decode(x) if f else x, "new": f.decode(y) if f else y,
                               "confidence": f.confidence if f else "UNKNOWN"})
    # header bytes before the settings array, compared positionally only when forms match
    if a.is_upload_form == b.is_upload_form:
        bk = {OFF_NEXT_PTR, OFF_NEXT_PTR + 1} | {a.settings_offset - 10 + i for i in range(4)}  # save ts
        n = min(a.settings_offset, b.settings_offset)
        for i in range(n):
            if ra[i] != rb[i]:
                if i in bk:
                    d.bookkeeping.append(i)
                else:
                    d.header.append({"offset": f"+0x{i:03x}", "old": f"{ra[i]:02x}", "new": f"{rb[i]:02x}"})
        # assistant area
        aa, ab = a.assistant_area, b.assistant_area
        if aa != ab:
            d.assistant = sum(1 for x, y in zip(aa, ab) if x != y) + abs(len(aa) - len(ab))
    else:
        # cannot compare assistant bytes across forms (padding differs); compare record structure instead
        from .assistants import parse_assistant_area
        ka = parse_assistant_area(a)["kind"]
        kb = parse_assistant_area(b)["kind"]
        d.assistant = 0 if ka == kb else 1
    # checksum trailer counted as bookkeeping when it differs
    if ra[-4:] != rb[-4:]:
        d.bookkeeping.extend(range(len(ra) - 4, len(ra)))
    return d


def diff_bytes(data_a: bytes, data_b: bytes) -> FileDiff:
    fa, fb = RvmsFile.parse(data_a), RvmsFile.parse(data_b)
    ua, ub = units_by_serial(fa), units_by_serial(fb)
    pro_a = fa.magic_raw + b"".join(s.raw for s in fa.sections if not s.is_unit)
    pro_b = fb.magic_raw + b"".join(s.raw for s in fb.sections if not s.is_unit)
    # BareSettingInfo carries its own pointer to the first unit block, which is position independent; the
    # Mk2vscInfo/BareSettingInfo payloads are what we call the prologue.
    pro_same = [s.payload for s in fa.sections if not s.is_unit] == [s.payload for s in fb.sections if not s.is_unit]
    units = [_classify(ua[s], ub[s]) for s in sorted(set(ua) & set(ub))]
    return FileDiff(identical=(data_a == data_b), length_a=len(data_a), length_b=len(data_b),
                    prologue_identical=pro_same, only_in_a=sorted(set(ua) - set(ub)),
                    only_in_b=sorted(set(ub) - set(ua)), units=units)


def diff_files(path_a: str, path_b: str) -> FileDiff:
    with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
        return diff_bytes(fa.read(), fb.read())


def render(d: FileDiff) -> str:
    if d.identical:
        return "identical"
    lines = [f"lengths {d.length_a} -> {d.length_b}; prologue {'same' if d.prologue_identical else 'DIFFERS'}; "
             f"verdict: {'ONLY BOOKKEEPING (settings verbatim)' if d.only_bookkeeping else 'CONTENT CHANGED'}"]
    for s in d.only_in_a:
        lines.append(f"  {s}: only in A")
    for s in d.only_in_b:
        lines.append(f"  {s}: only in B")
    for u in d.units:
        lines.append(f"  {u.serial}: len {u.length_a}->{u.length_b} form {u.form_a}->{u.form_b} "
                     f"bookkeeping={len(u.bookkeeping)}B header={len(u.header)}B assistant={u.assistant}B"
                     + (f"  [{u.note}]" if u.note else ""))
        for s in u.settings:
            lines.append(f"      setting {s['id']:3d} {s['name'] or '?':28s} {s['old']} -> {s['new']}  [{s['confidence']}]")
        for h in u.header[:12]:
            lines.append(f"      header {h['offset']}: {h['old']} -> {h['new']}")
        if len(u.header) > 12:
            lines.append(f"      ... {len(u.header)-12} more header bytes")
    return "\n".join(lines)
