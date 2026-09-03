"""
Decode a ``.rvms`` into a plain dictionary: file structure, per-inverter identity, every setting with
its label/confidence, and the assistant area summary.  JSON-serialisable.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .sections import RvmsFile
from .units import unit_blocks, N_SETTINGS
from .fields import BY_ID, UNKNOWN
from .assistants import parse_assistant_area


def decode_bytes(data: bytes, include_unknown: bool = True, include_raw_settings: bool = False) -> Dict:
    f = RvmsFile.parse(data)
    out: Dict = {
        "length": f.length,
        "sections": [
            {"name": s.name.decode(), "start": s.start, "next": s.next_ptr, "payload_bytes": len(s.payload),
             "checksum_stored": f"{s.stored_checksum:08x}", "checksum_computed": f"{s.computed_checksum:08x}",
             "checksum_ok": s.checksum_ok}
            for s in f.sections
        ],
        "all_checksums_ok": f.all_checksums_ok,
        "units": [],
    }
    mk = f.section(b"Mk2vscInfo")
    try:
        vlen = int.from_bytes(mk.payload[4:6], "little")
        out["format_version"] = mk.payload[6: 6 + vlen].decode()
    except Exception:  # pragma: no cover - malformed header
        out["format_version"] = None

    for u in unit_blocks(f):
        d = u.summary()
        settings = u.settings()
        named: List[Dict] = []
        for sid in range(N_SETTINGS):
            raw = settings[sid]
            fld = BY_ID.get(sid)
            if fld is None:
                if not include_unknown:
                    continue
                named.append({"id": sid, "offset": f"+0x{u.setting_offset(sid):03x}", "raw": raw,
                              "name": None, "confidence": UNKNOWN})
                continue
            if fld.confidence == UNKNOWN and not include_unknown:
                continue
            entry = {"id": sid, "offset": f"+0x{u.setting_offset(sid):03x}", "raw": raw, "name": fld.name,
                     "label": fld.label, "value": fld.decode(raw), "unit": fld.unit, "confidence": fld.confidence}
            if fld.bits:
                entry["bits_set"] = [fld.bits[b] for b in fld.bits if raw & (1 << b)]
            named.append(entry)
        d["settings"] = named
        if include_raw_settings:
            d["settings_raw"] = settings
        d["assistant"] = parse_assistant_area(u)
        out["units"].append(d)
    return out


def decode_file(path: str, **kw) -> Dict:
    with open(path, "rb") as fh:
        return decode_bytes(fh.read(), **kw)


def brief(d: Dict) -> str:
    """Human-readable one-screen summary of a decoded file."""
    lines = [f"format {d.get('format_version')}  length {d['length']}  checksums {'OK' if d['all_checksums_ok'] else 'BAD'}"]
    for u in d["units"]:
        a = u["assistant"]
        lines.append(f"  {u['serial']}  fw {u['firmware']}  form={u['form']}  flag={u['assistant_flag']}  "
                     f"saved {u['save_time_utc']}  assistant: {a['summary']}")
        for s in u["settings"]:
            if s.get("name") and s["confidence"] in ("CONFIRMED", "HIGH"):
                v = s["value"]
                lines.append(f"      {s['name']:28s} {v!s:>8} {s['unit']:4s} [{s['confidence']}] ({s['offset']})")
    return "\n".join(lines)
