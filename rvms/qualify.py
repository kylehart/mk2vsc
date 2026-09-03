"""
Qualify a file against *intended* values before upload and after re-download.

Why: structural validity is not correctness.  A file that passes every checksum and every diff
guard can still carry the wrong settings.  We learned this by uploading a rollback built from a month-old
baseline that silently re-introduced an out-of-spec charge voltage on one inverter; every structural
check passed and nobody noticed for a month.  The fix is to keep the intended values *outside* the
file under test and check the file against them, every time.

An intent file is JSON (or a dict)::

    {
      "system": "house-2",
      "serials": ["HQ2414U6FVN", "HQ2414AXENJ"],         # optional: fail if the file is for another system
      "settings": {"absorption_V": 56.8, "float_V": 54.0, "vs_accept_battery_above_V": 52.5},
      "require_agreement": true,                           # inverters must agree on CONFIRMED fields (HIGH -> warning)
      "agreement_fields": ["absorption_V", "float_V"]      # optional: fields that must agree (adds FAIL for these)
    }

Exit status semantics for the CLI: 0 = QUALIFIED, 1 = NOT QUALIFIED.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .sections import RvmsFile
from .units import units_by_serial
from .fields import lookup, FIELDS, CONFIRMED, HIGH

EPS = 0.005


@dataclass
class Intent:
    settings: Dict[str, float]
    serials: Optional[List[str]] = None
    system: str = ""
    require_agreement: bool = True
    agreement_fields: Optional[List[str]] = None   # ADDITIONAL fields that must agree (CONFIRMED always must; HIGH only warns)

    @classmethod
    def load(cls, path: str) -> "Intent":
        with open(path) as fh:
            d = json.load(fh)
        return cls(settings=d.get("settings", {}), serials=d.get("serials"), system=d.get("system", ""),
                   require_agreement=d.get("require_agreement", True), agreement_fields=d.get("agreement_fields"))


def qualify_bytes(data: bytes, intent: Intent) -> Tuple[bool, List[Tuple[str, str]]]:
    results: List[Tuple[str, str]] = []
    ok = True
    try:
        f = RvmsFile.parse(data)
    except Exception as e:  # noqa: BLE001
        return False, [("FAIL", f"not parseable: {e}")]
    for name, start, stored, computed, valid in f.checksum_report():
        if not valid:
            ok = False
            results.append(("FAIL", f"checksum invalid in {name} @0x{start:x} (stored {stored:08x}, computed {computed:08x})"))
    if ok:
        results.append(("PASS", "all section checksums valid"))
    units = units_by_serial(f)
    results.append(("INFO", f"{len(units)} inverter block(s): {', '.join(sorted(units))}"))
    if intent.serials:
        want = set(intent.serials)
        if set(units) != want:
            ok = False
            results.append(("FAIL", f"serials {sorted(units)} != intended {sorted(want)} -- wrong system?"))
        else:
            results.append(("PASS", "serials match the intended system"))
    for u in units.values():
        if u.is_upload_form:
            results.append(("WARN", f"{u.serial}: upload-form block (GUI export), not a device download"))
        if b"\x40\x00\xa7\xfe" in u.assistant_area:
            ok = False
            results.append(("FAIL", f"{u.serial}: empty assistant STUB present (failed by-file install signature)"))

    agree_names = [x.name for x in FIELDS if x.confidence in (CONFIRMED, HIGH) and x.bits is None]
    for extra in intent.agreement_fields or []:
        if lookup(extra).name not in agree_names:
            agree_names.append(lookup(extra).name)
    if intent.require_agreement and len(units) > 1:
        for name in agree_names:
            fld = lookup(name)
            vals = {s: fld.decode(u.setting(fld.id)) for s, u in units.items()}
            if len(set(vals.values())) > 1:
                detail = ", ".join(f"{s}={v}" for s, v in vals.items())
                if fld.confidence == CONFIRMED or name in (intent.agreement_fields or ()):
                    ok = False
                    results.append(("FAIL", f"{name}: inverters DISAGREE ({detail})"))
                else:
                    results.append(("WARN", f"{name}: inverters differ ({detail}) -- not required to match, but check it is intended"))
    for name, target in intent.settings.items():
        fld = lookup(name)
        bad = []
        for s, u in units.items():
            v = fld.decode(u.setting(fld.id))
            if abs(v - target) > EPS:
                bad.append(f"{s}={v}")
        if bad:
            ok = False
            results.append(("FAIL", f"{name}: expected {target}, got {', '.join(bad)}"))
        else:
            results.append(("PASS", f"{name} = {target} on all inverters"))
    if not intent.settings:
        results.append(("WARN", "intent lists no settings; only structure and agreement were checked"))
    return ok, results


def qualify_file(path: str, intent: Intent):
    with open(path, "rb") as fh:
        return qualify_bytes(fh.read(), intent)


def render(ok: bool, results, path: str = "") -> str:
    mark = {"PASS": "  ok  ", "FAIL": "  FAIL", "WARN": "  warn", "INFO": "  ..  "}
    lines = [f"{path}: {'QUALIFIED' if ok else 'NOT QUALIFIED'}"]
    lines += [f"{mark[l]} {m}" for l, m in results]
    return "\n".join(lines)
