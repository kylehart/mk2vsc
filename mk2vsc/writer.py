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
from .fields import lookup, CONFIRMED, HIGH, Field, BY_NAME, DC_VOLT_IDS
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
    bit: Optional[int] = None        # set for a bit-level edit of a flag register; the raws are whole words

    def as_dict(self) -> Dict:
        d = {"serial": self.serial, "field": self.field.name, "id": self.field.id,
             "old": self.field.decode(self.old_raw), "new": self.field.decode(self.new_raw),
             "unit": self.field.unit, "block_offset": f"+0x{self.offset_in_block:03x}",
             "file_offset": f"0x{self.offset_in_file:04x}"}
        if self.bit is not None:
            d.update({"bit": self.bit, "bit_name": (self.field.bits or {}).get(self.bit, ""),
                      "old": f"0x{self.old_raw:04x}", "new": f"0x{self.new_raw:04x}"})
        return d


def set_settings(data: bytes, changes: Iterable[Tuple[Optional[str], object, object]],
                 allow_unverified: bool = False, allow_out_of_range: bool = False) -> Tuple[bytes, List[Edit]]:
    """Apply ``changes`` = [(serial_or_None, field_name_or_id, value)] and return ``(new_bytes, edits)``.

    ``serial=None`` means every inverter in the file (the common case: charge voltages must match on
    a shared battery).  ``value`` is in engineering units (volts, amps, percent) or a raw int for
    unscaled fields.  Raises ``WriteRefused`` rather than emit a file it cannot prove correct.
    """
    f, by_serial, schema, nominal = _prepare(data)
    volt_scale = nominal / 48.0          # Field.lo/hi are written for a 48 V system; DC voltage bounds scale with nominal
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
            k = volt_scale if (fld.unit == "V" and fld.id in DC_VOLT_IDS) else 1.0   # AC bounds do not scale
            lo, hi = fld.lo * k, fld.hi * k
            if not (lo <= fld.decode(new_raw) <= hi):
                raise WriteRefused(f"{fld.name}={fld.decode(new_raw)} {fld.unit} is outside the plausible range "
                                   f"{lo:g}..{hi:g} for a {nominal} V system; pass allow_out_of_range=True if you mean it")
        targets = list(by_serial.values()) if serial is None else [by_serial[serial]] if serial in by_serial else None
        if targets is None:
            raise WriteRefused(f"serial {serial} not in file (have {sorted(by_serial)})")
        for u in targets:
            edits.append(_poke(f, payloads, touched_sections, u, fld, new_raw))

    new_file = f.rebuild(payloads)

    # ---- cross-field sanity on the RESULT: float must not exceed absorption on any inverter ----
    if not allow_out_of_range:
        for u in units_by_serial(new_file).values():
            a, fl = u.setting(BY_NAME["absorption_V"].id) / 100, u.setting(BY_NAME["float_V"].id) / 100
            if fl > a + 0.005 and a > 0:
                raise WriteRefused(f"{u.serial}: float {fl} V would exceed absorption {a} V; refusing")
    return _verified(f, data, new_file, edits, touched_sections), edits


def _prepare(data: bytes):
    """Every guard that applies before any edit: parse, checksums, device form, no stub, schema, nominal
    voltage, alignment.  Returns ``(file, units_by_serial, schema, nominal_voltage)``."""
    f = RvmsFile.parse(data)
    if not f.all_checksums_ok:
        bad = [n for n, *_ , ok in f.checksum_report() if not ok]
        raise WriteRefused(f"input file has invalid checksums in {bad}; refusing to build on a corrupt base")
    by_serial = units_by_serial(f)
    schema = schema_of(f)
    return (f, by_serial, schema, preflight(by_serial, schema))


def preflight(by_serial, schema) -> int:
    """The guards that need parsed state: device form, no stub, a known nominal voltage, alignment.  Returns the
    nominal voltage.  ``_prepare`` runs it after parsing; the diagnose context runs it on state it already holds."""
    if any(u.is_upload_form for u in by_serial.values()):
        raise WriteRefused("input is in GUI upload form (blob at +0x45); edit a device download instead")
    stubbed = [u.serial for u in by_serial.values() if parse_assistant_area(u)["stub"]]
    if stubbed:
        raise WriteRefused(f"{stubbed} carry the empty assistant STUB of a failed by-file install; restore the "
                           "system from a fresh bare download before editing settings")
    try:
        nominal = nominal_voltage(schema)
    except ValueError as e:
        raise WriteRefused(f"{e}; refusing to apply plausibility bounds to an unrecognised system")
    from .align import check as align_check
    for u in by_serial.values():
        al = align_check(u, schema)
        if not al.ok:
            raise WriteRefused(f"{u.serial}: settings array does not sit where the layout model expects "
                               f"({al.summary}); this file's layout is not one this writer knows, refusing")
    return nominal


def _poke(f: RvmsFile, payloads: List[bytes], touched: set, u, fld: Field, new_raw: int, bit: Optional[int] = None) -> Edit:
    """Write one u16 into one block's payload copy and record the edit."""
    off = u.setting_offset(fld.id)                 # relative to name start
    sec = u.section
    sec_idx = f.sections.index(sec)
    # payload offset: name start is section.start+2; payload starts at start+2+len(name)+4
    p_off = off - (len(sec.name) + 4)
    pl = bytearray(payloads[sec_idx])
    old_raw = int.from_bytes(pl[p_off: p_off + 2], "little")
    pl[p_off: p_off + 2] = new_raw.to_bytes(2, "little")
    payloads[sec_idx] = bytes(pl)
    touched.add(sec_idx)
    return Edit(u.serial, fld, old_raw, new_raw, off, sec.name_start + off, bit)


def _verified(f: RvmsFile, data: bytes, new_file: RvmsFile, edits: List[Edit], touched_sections: set) -> bytes:
    """Length, checksums, and a byte-diff limited to the intended words and their section checksums."""
    out = new_file.to_bytes()
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
    return out


# Flag bits the writer will set or clear without an override.  A bit qualifies when the corpus or a device
# holds a before/after flip of exactly that bit, authored by VEConfigure or the device, on a system that
# subsequently ran, with no other bit of the register changing (docs/DIAGNOSE.md, decision 2).
QUALIFIED_BITS: Dict[Tuple[str, int], str] = {
    ("flags2", 4): "LithiumBattery: System A unit 1 reads the bit set since its June 2026 commissioning download "
                   "(GUI-authored, running system); every lithium-commissioned block in the corpus reads it set.",
}


def set_bits(data: bytes, changes: Iterable[Tuple[Optional[str], object, int, bool]],
             allow_unqualified: bool = False) -> Tuple[bytes, List[Edit]]:
    """Set or clear single bits of the flag registers: ``changes`` = [(serial_or_None, field, bit, set)].

    Read-modify-write on the whole word; only the target bit changes.  The bit must be inside the
    register's settable mask (the schema's ``max`` for a flag register) and, unless ``allow_unqualified``,
    listed in ``QUALIFIED_BITS``.  The whole-word range check is deliberately skipped: observed flags0 words
    (0x81f4 on every device block, bit 15 set) exceed the 0x6ffc mask, so it would refuse every file.
    Same guards and byte-diff proof as ``set_settings`` otherwise.
    """
    f, by_serial, schema, _nominal = _prepare(data)
    payloads = [s.payload for s in f.sections]
    edits: List[Edit] = []
    touched: set = set()
    for serial, name, bit, on in changes:
        fld = lookup(name)
        if fld.bits is None:
            raise WriteRefused(f"{fld.name} is not a flag register; use set_settings for values")
        if not 0 <= int(bit) <= 15:
            raise WriteRefused(f"bit {bit} outside 0..15")
        mask = schema[fld.id].max
        if not (1 << bit) & mask:
            raise WriteRefused(f"{fld.name} bit {bit} is not in the register's settable mask 0x{mask:04x} "
                               f"(the schema's max for a flag register); refusing")
        if (fld.name, int(bit)) not in QUALIFIED_BITS and not allow_unqualified:
            known = (fld.bits or {}).get(int(bit), "unnamed")
            raise WriteRefused(f"{fld.name} bit {bit} ({known}) is not a qualified bit: no VEConfigure- or device-authored "
                               f"flip of exactly this bit on a running system is on record; pass allow_unqualified=True "
                               f"to be the first to try it")
        targets = list(by_serial.values()) if serial is None else [by_serial[serial]] if serial in by_serial else None
        if targets is None:
            raise WriteRefused(f"serial {serial} not in file (have {sorted(by_serial)})")
        for u in targets:
            sec_idx = f.sections.index(u.section)
            p_off = u.setting_offset(fld.id) - (len(u.section.name) + 4)
            cur = int.from_bytes(payloads[sec_idx][p_off: p_off + 2], "little")
            new_raw = (cur | (1 << bit)) if on else (cur & ~(1 << bit) & 0xFFFF)
            edits.append(_poke(f, payloads, touched, u, fld, new_raw, bit=int(bit)))
    new_file = f.rebuild(payloads)
    return _verified(f, data, new_file, edits, touched), edits


def set_settings_file(in_path: str, out_path: str, changes, allow_unverified: bool = False,
                      allow_out_of_range: bool = False) -> List[Edit]:
    with open(in_path, "rb") as fh:
        data = fh.read()
    out, edits = set_settings(data, changes, allow_unverified=allow_unverified, allow_out_of_range=allow_out_of_range)
    with open(out_path, "wb") as fh:
        fh.write(out)
    return edits
