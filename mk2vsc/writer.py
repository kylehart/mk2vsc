"""
Guarded, self-verifying editor for values in the settings array.

The only class of edit this project has ever applied to live hardware without incident is a
**length-preserving change to a u16 in the settings array** of an existing block, with the section
checksum recomputed.  ``set_settings`` does exactly that and nothing else:

* it edits by inverter **serial** (block order is not stable across downloads);
* it refuses fields below HIGH confidence unless ``allow_unverified=True``;
* it refuses to change file length or any byte outside the target settings + the touched checksums;
* it re-parses its own output and proves the diff is limited to the intended bytes before returning;
* it never uploads.  You upload through VRM's Remote VEConfigure, then re-download and ``diff``.

Uploading a file **replaces the whole configuration of every inverter** in the system.  Build every
edit on a *fresh* download (archived files have been refused with ``mk2vsc-36``; docs/ERRORS.md) and expect
that any field you edited earlier is only as current as the file you start from.  See docs/CHANGE_CONTROL.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from .sections import RvmsFile
from .units import units_by_serial, unit_blocks
from .fields import lookup, CONFIRMED, HIGH, Field, BY_NAME
from .assistants import parse_assistant_area
from .schema import schema_of, nominal_voltage


class WriteRefused(RuntimeError):
    """The requested edit is outside the proven-safe surface, or verification failed."""


@dataclass
class Edit:
    serial: str
    field: Field
    old_raw: int
    new_raw: int
    offset_in_block: int
    offset_in_file: int

    def as_dict(self) -> Dict:
        return {"serial": self.serial, "field": self.field.name, "id": self.field.id,
                "old": self.field.decode(self.old_raw), "new": self.field.decode(self.new_raw),
                "unit": self.field.unit, "block_offset": f"+0x{self.offset_in_block:03x}",
                "file_offset": f"0x{self.offset_in_file:04x}"}


def set_settings(data: bytes, changes: Iterable[Tuple[Optional[str], object, object]],
                 allow_unverified: bool = False, allow_out_of_range: bool = False) -> Tuple[bytes, List[Edit]]:
    """Apply ``changes`` = [(serial_or_None, field_name_or_id, value)] and return ``(new_bytes, edits)``.

    ``serial=None`` means every inverter in the file (the common case: charge voltages must match on
    a shared battery).  ``value`` is in engineering units (volts, amps, percent) or a raw int for
    unscaled fields.  Raises ``WriteRefused`` rather than emit a file it cannot prove correct.
    """
    f = RvmsFile.parse(data)
    if not f.all_checksums_ok:
        bad = [n for n, *_ , ok in f.checksum_report() if not ok]
        raise WriteRefused(f"input file has invalid checksums in {bad}; refusing to build on a corrupt base")
    by_serial = units_by_serial(f)
    if any(u.is_upload_form for u in by_serial.values()):
        raise WriteRefused("input is in GUI upload form (blob at +0x45); edit a device download instead")
    stubbed = [u.serial for u in by_serial.values() if parse_assistant_area(u)["stub"]]
    if stubbed:
        raise WriteRefused(f"{stubbed} carry the empty assistant STUB of a failed by-file install; restore the "
                           "system from a fresh bare download before editing settings")

    schema = schema_of(f)
    try:
        nominal = nominal_voltage(schema)
    except ValueError as e:
        raise WriteRefused(f"{e}; refusing to apply plausibility bounds to an unrecognised system")
    volt_scale = nominal / 48.0          # Field.lo/hi are written for a 48 V system; voltage bounds scale with nominal
    from .align import check as align_check
    for u in by_serial.values():
        al = align_check(u, schema)
        if not al.ok:
            raise WriteRefused(f"{u.serial}: settings array does not sit where the layout model expects "
                               f"({al.summary}); this file's layout is not one this writer knows, refusing")
    payloads = [s.payload for s in f.sections]
    edits: List[Edit] = []
    touched_sections = set()
    for serial, name, value in changes:
        fld = lookup(name)
        if fld.confidence not in (CONFIRMED, HIGH) and not allow_unverified:
            raise WriteRefused(f"{fld.name} is {fld.confidence}; pass allow_unverified=True to edit it anyway")
        if fld.bits is not None:
            raise WriteRefused(f"{fld.name} is a flag register; bit-level editing is not supported")
        try:
            new_raw = fld.encode(value)
        except ValueError as e:
            raise WriteRefused(str(e))
        if fld.scale == 1.0 and not fld.period and float(value) != float(fld.decode(new_raw)):
            raise WriteRefused(f"{fld.name} is an integer field; {value} would be rounded to {fld.decode(new_raw)}")
        info = schema[fld.id]
        if not allow_out_of_range and not info.unused and not info.in_range(new_raw):
            raise WriteRefused(f"{fld.name}: raw {new_raw} is outside the device's own range {info.min}..{info.max} "
                               f"({fld.decode(info.min)}..{fld.decode(info.max)} {fld.unit}) from BareSettingInfo")
        if not allow_out_of_range and fld.lo is not None:
            k = volt_scale if fld.unit == "V" else 1.0
            lo, hi = fld.lo * k, fld.hi * k
            if not (lo <= fld.decode(new_raw) <= hi):
                raise WriteRefused(f"{fld.name}={fld.decode(new_raw)} {fld.unit} is outside the plausible range "
                                   f"{lo:g}..{hi:g} for a {nominal} V system; pass allow_out_of_range=True if you mean it")
        targets = list(by_serial.values()) if serial is None else [by_serial[serial]] if serial in by_serial else None
        if targets is None:
            raise WriteRefused(f"serial {serial} not in file (have {sorted(by_serial)})")
        for u in targets:
            off = u.setting_offset(fld.id)                 # relative to name start
            sec = u.section
            sec_idx = f.sections.index(sec)
            # payload offset: name start is section.start+2; payload starts at start+2+len(name)+4
            p_off = off - (len(sec.name) + 4)
            pl = bytearray(payloads[sec_idx])
            old_raw = int.from_bytes(pl[p_off: p_off + 2], "little")
            pl[p_off: p_off + 2] = new_raw.to_bytes(2, "little")
            payloads[sec_idx] = bytes(pl)
            touched_sections.add(sec_idx)
            edits.append(Edit(u.serial, fld, old_raw, new_raw, off, sec.name_start + off))

    new_file = f.rebuild(payloads)
    out = new_file.to_bytes()

    # ---- cross-field sanity on the RESULT: float must not exceed absorption on any inverter ----
    if not allow_out_of_range:
        for u in units_by_serial(new_file).values():
            a, fl = u.setting(BY_NAME["absorption_V"].id) / 100, u.setting(BY_NAME["float_V"].id) / 100
            if fl > a + 0.005 and a > 0:
                raise WriteRefused(f"{u.serial}: float {fl} V would exceed absorption {a} V; refusing")

    # ---- verification: length, checksums, and a byte-diff limited to what we intended ----
    if len(out) != len(data):
        raise WriteRefused("length changed during a value edit -- internal error, refusing to write")
    chk = RvmsFile.parse(out)
    if not chk.all_checksums_ok:
        raise WriteRefused("output checksums do not validate -- internal error")
    allowed = set()
    for e in edits:
        allowed.update({e.offset_in_file, e.offset_in_file + 1})
    for idx in touched_sections:
        c = chk.sections[idx].checksum_offset
        allowed.update({c, c + 1, c + 2, c + 3})
    stray = [i for i in range(len(out)) if out[i] != data[i] and i not in allowed]
    if stray:
        raise WriteRefused(f"unexpected byte changes at {[hex(i) for i in stray[:8]]} -- refusing to write")
    # pointers must be untouched (same length -> same chain)
    for a, b in zip(f.sections, chk.sections):
        if a.next_ptr != b.next_ptr:
            raise WriteRefused("section pointer changed -- internal error")
    return out, edits


def set_settings_file(in_path: str, out_path: str, changes, allow_unverified: bool = False,
                      allow_out_of_range: bool = False) -> List[Edit]:
    with open(in_path, "rb") as fh:
        data = fh.read()
    out, edits = set_settings(data, changes, allow_unverified=allow_unverified, allow_out_of_range=allow_out_of_range)
    with open(out_path, "wb") as fh:
        fh.write(out)
    return edits
