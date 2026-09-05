"""The census report: everything needed to judge whether the format model holds on a file, without the file."""
from __future__ import annotations

from typing import Tuple

from .sections import RvmsFile, RvmsParseError
from .units import unit_blocks
from .assistants import parse_assistant_area, grid_code_words
from .schema import schema_of, firmware_of_schema
from .fields import BY_ID

KEY_SETTINGS = [2, 3, 4, 5, 6, 11, 54, 58, 62, 64, 65]


def census_text(data: bytes, name: str) -> Tuple[str, bool]:
    """``(text, ok)``: the block ``mk2vsc census`` prints for one file.  ``ok`` is False when the file does not
    parse, a checksum fails, the schema is unusable, a block is misaligned, or there is no inverter block."""
    try:
        f = RvmsFile.parse(data)
    except RvmsParseError as e:
        return f"{name}: PARSE FAILED: {e}", False
    lines = []
    ok = True
    cks = "OK" if f.all_checksums_ok else "INVALID"
    try:
        mk = f.section(b"Mk2vscInfo").payload
        version = mk[6: 6 + int.from_bytes(mk[4:6], "little")].decode()
    except Exception:  # noqa: BLE001
        version = "?"
    try:
        sch = schema_of(f)
        info_fw = firmware_of_schema(f.section(b"BareSettingInfo").payload)
        schema_txt = f"parsed ({len(sch)} records, firmware {info_fw})"
    except Exception as e:  # noqa: BLE001
        sch = None
        schema_txt = f"NOT PARSED ({e})"
    units = unit_blocks(f)
    lines.append(f"{name}: {f.length} bytes, {len(f.sections)} sections, checksums {cks}, "
                 f"format {version}, schema {schema_txt}, {len(units)} inverter(s)")
    for u in units:
        asst = parse_assistant_area(u)
        gcw = grid_code_words(u)
        in_range = ""
        if sch is not None:
            from .align import check as align_check
            al = align_check(u, sch)
            in_range = ", " + al.summary
            if not al.ok:
                ok = False
        when = u.save_datetime.isoformat() if u.save_datetime else "?"
        lines.append(f"  {u.serial}: block {len(u.raw)} B, flag {u.assistant_flag:02x}, form {'upload' if u.is_upload_form else 'device'}, "
                     f"firmware {u.firmware_version}, saved {when}, assistant: {asst['summary']}; {gcw['summary']}{in_range}")
        cells = []
        for k in KEY_SETTINGS:
            fld = BY_ID[k]
            v = fld.decode(u.setting(k))
            cells.append(f"{fld.name}={v:g}{fld.unit}" if isinstance(v, float) else f"{fld.name}={v}{fld.unit}")
        lines.append("    " + "  ".join(cells))
    if not f.all_checksums_ok or sch is None or len(units) == 0:
        ok = False
    return "\n".join(lines), ok
