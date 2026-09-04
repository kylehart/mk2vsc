"""
EXPERIMENTAL: build a file that carries the ESS assistant on both inverters of a bare two-inverter system,
by grafting the assistant records from a known-good device download (the *template*) onto the target's
own bare download (the *baseline*).

STATUS (2026-09-03): every file this produced was ACCEPTED by the device and STORED byte-perfect, and
the resulting system NEVER STARTED (it sits Off, "connecting", no error).  One variant was
accepted and then replaced by an empty 64-byte stub.  Read docs/ESS_INJECTION.md before using this on
hardware.  It is published so that someone can pick up where we left off, not because it works.

What it does (the "v3 + v7" recipe, the last one we tried):

1. Keep the target's bare block verbatim up to the assistant area (identity, timestamp, all settings).
2. Append the template's assistant area from the slot-matched template block (the 704-byte record for
   one slot, the 1152-byte record for the other, plus the template's 72-byte tail).
3. Flip the assistant flag at +0x36 (f4 -> e4, f5 -> e5).
4. Optionally apply the "install state": the set of ordinary settings that every GUI ESS install was
   observed to write.  In setting-ID terms (we did not know this when we found them by byte offset):

       flags0 bit 11 cleared        (adaptive charge curve off; +0x5a 0x89 -> 0x81)
       setting 7  = 2               (repeated absorption time)
       setting 8  = 4               (repeated absorption interval)
       setting 10 = 1               (charge characteristic: fixed)
       setting 15 = 0               (unknown toggle)
       setting 60 = 48              (solar & wind priority flags)
       setting 62 low byte = 0xc3   (output frequency period word 41666 -> 41667, both 60.00 Hz)
       setting 64 = 300             (battery capacity, Ah -- the template system's value!)
       setting 81 = 1               (grid code active)
       setting 128 = 1              (LOM configuration A)

   Note setting 64: the GUI wizard writes the capacity the operator typed.  Stamping 300 Ah onto a
   200 Ah system is wrong; pass ``capacity_ah`` to override, or leave install_state off.
5. Recompute pointers and checksums (sections.rebuild).

Everything the function returns is self-checked: two blocks, both flagged, target serials only, no
upload-form blob, records byte-identical to the template's, headers preserved except the intended bytes.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from ..sections import RvmsFile, SECTION_DATA
from ..units import unit_blocks, units_by_serial, UnitBlock, OFF_ASSISTANT_FLAG, BARE_FLAGS, ASSISTANT_FLAGS
from ..assistants import parse_assistant_area
from ..fields import BY_NAME

ASSIST_ON = {0xF4: 0xE4, 0xF5: 0xE5}

# The install-state writes, by setting ID (see module docstring).  Byte-level fields are expressed as
# (id, mask, value) so a partial-word write stays explicit.
INSTALL_STATE = [
    ("flags0", 0x0800, 0x0000),            # clear bit 11 (adaptive charge curve)
    ("repeated_absorption_time", None, 2),
    ("repeated_absorption_interval", None, 4),
    ("charge_characteristic", None, 1),
    ("unknown_toggle_15", None, 0),
    ("solar_wind_priority_flags", None, 48),
    ("output_frequency_Hz", 0x00FF, 0x00C3),   # low byte of the period word: 41666 -> 41667
    ("battery_capacity_Ah", None, 300),
    ("grid_code_active", None, 1),
    ("lom_config_a", None, 1),
]


class GraftRefused(RuntimeError):
    pass


def _check(cond: bool, msg: str):
    if not cond:
        raise GraftRefused(msg)


def graft(baseline: bytes, template: bytes, install_state: bool = False,
          capacity_ah: Optional[int] = None) -> Tuple[bytes, Dict]:
    """Return ``(grafted_bytes, checks)``.  Raises ``GraftRefused`` if inputs are not what the recipe expects."""
    fb, ft = RvmsFile.parse(baseline), RvmsFile.parse(template)
    _check(fb.all_checksums_ok, "baseline checksums invalid; re-download it")
    _check(ft.all_checksums_ok, "template checksums invalid")
    bu, tu = unit_blocks(fb), unit_blocks(ft)
    _check(len(bu) == 2 and len(tu) == 2, "recipe is for two-inverter systems")
    _check(all(u.assistant_flag in BARE_FLAGS for u in bu), "baseline already carries an assistant flag")
    _check(all(u.assistant_flag in ASSISTANT_FLAGS for u in tu), "template must have the assistant on both inverters")
    _check(not any(u.is_upload_form for u in bu + tu), "both inputs must be device-form downloads (no blob at +0x45)")
    tpl_areas = {u.slot: parse_assistant_area(u) for u in tu}
    _check(all(a["kind"] == "records" for a in tpl_areas.values()), "template blocks must carry assistant records")
    _check([s.payload for s in fb.sections if not s.is_unit] == [s.payload for s in ft.sections if not s.is_unit],
           "prologue (Mk2vscInfo/BareSettingInfo) differs between baseline and template")
    tpl_by_slot = {u.slot: u for u in tu}
    _check(len(tpl_by_slot) == 2, "template blocks share a slot")

    payloads = []
    for s in fb.sections:
        if not s.is_unit:
            payloads.append(s.payload)
            continue
        u = next(x for x in bu if x.section is s)
        src = tpl_by_slot.get(u.slot)
        _check(src is not None, f"no template block for slot {u.slot}")
        hdr_len = len(SECTION_DATA) + 4                      # name + next-pointer, not in payload
        body = bytearray(u.raw[hdr_len: u.assistant_area_offset])   # payload up to the assistant area
        body[OFF_ASSISTANT_FLAG - hdr_len] = ASSIST_ON[u.assistant_flag]
        if install_state:
            for name, mask, value in INSTALL_STATE:
                fld = BY_NAME[name]
                off = u.setting_offset(fld.id) - hdr_len
                cur = int.from_bytes(body[off: off + 2], "little")
                if name == "battery_capacity_Ah" and capacity_ah is not None:
                    value = capacity_ah
                new = value if mask is None else (cur & ~mask) | (value & mask)
                body[off: off + 2] = new.to_bytes(2, "little")
        body += src.assistant_area
        payloads.append(bytes(body))
    out_file = fb.rebuild(payloads)
    out = out_file.to_bytes()
    checks = _verify(out, baseline, template, install_state)
    return out, checks


def _verify(out: bytes, baseline: bytes, template: bytes, install_state: bool) -> Dict:
    fo, fb, ft = RvmsFile.parse(out), RvmsFile.parse(baseline), RvmsFile.parse(template)
    ou, bu, tu = units_by_serial(fo), units_by_serial(fb), {u.slot: u for u in unit_blocks(ft)}
    c: Dict[str, bool] = {}
    c["checksums_valid"] = fo.all_checksums_ok
    c["two_blocks"] = len(ou) == 2
    c["serials_are_target"] = set(ou) == set(bu)
    c["assistant_flag_on_both"] = all(u.assistant_flag in ASSISTANT_FLAGS for u in ou.values())
    c["no_upload_blob"] = not any(u.is_upload_form for u in ou.values())
    c["records_match_template"] = all(
        u.assistant_area == tu[u.slot].assistant_area for u in ou.values())
    c["no_stub"] = not any(parse_assistant_area(u)["stub"] for u in ou.values())
    allowed_ids = {BY_NAME[n].id for n, _m, _v in INSTALL_STATE} if install_state else set()
    def header_ok(o: UnitBlock, b: UnitBlock) -> bool:
        n = o.assistant_area_offset
        for i in range(0x13, n):                      # after the next-pointer
            if o.raw[i] == b.raw[i]:
                continue
            if i == OFF_ASSISTANT_FLAG:
                continue
            if i >= o.settings_offset and (i - o.settings_offset) // 2 in allowed_ids:
                continue
            return False
        return True
    c["header_preserved"] = all(header_ok(ou[s], bu[s]) for s in ou)
    c["settings_preserved"] = all(
        [x for k, x in enumerate(ou[s].settings()) if k not in allowed_ids]
        == [x for k, x in enumerate(bu[s].settings()) if k not in allowed_ids] for s in ou)
    failed = [k for k, v in c.items() if not v]
    if failed:
        raise GraftRefused(f"self-check failed: {failed}")
    return c
