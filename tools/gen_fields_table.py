#!/usr/bin/env python3
"""Print the settings table in docs/FIELDS.md as Markdown, generated from mk2vsc/fields.py.

    PYTHONPATH=. python3 tools/gen_fields_table.py > /tmp/fields_table.md

The table in docs/FIELDS.md is pasted from this output so the document cannot drift from the code.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mk2vsc.fields import FIELDS  # noqa: E402
from mk2vsc.schema import schema_of  # noqa: E402
from mk2vsc.sections import RvmsFile  # noqa: E402
import glob  # noqa: E402

_FIX = sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "*", "*download_bare*.rvms")))
SCHEMA = schema_of(RvmsFile.load(_FIX[0])) if _FIX else None


def schema_cell(f):
    if SCHEMA is None:
        return ""
    r = SCHEMA[f.id]
    if r.unused:
        return "unused"
    fmt = lambda raw: (f"{f.decode(raw):g}" if f.scale != 1.0 or f.raw_offset or f.period else str(raw))
    return f"default {fmt(r.default)}; {fmt(r.min)} to {fmt(r.max)}"


def esc(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def main():
    print("| ID | Offset | Name | VEConfigure identifier | VEConfigure label | Type / scale | Unit | Confidence | Presumed usage | Evidence | Observed values | Device schema (default; min to max) |")
    print("|---:|:------:|------|------------------------|-------------------|--------------|------|:----------:|----------------|----------|-----------------|-------------------------------------|")
    for f in FIELDS:
        typ = "u16 bitmask" if f.bits else ("u16 / %g" % f.scale if f.scale != 1 else "u16")
        desc = f.description
        if f.bits:
            desc += " Bits: " + "; ".join(f"bit {b} = {m}" for b, m in sorted(f.bits.items())) + "."
        print(f"| {f.id} | +0x{f.offset:03x} | `{f.name}` | `{f.eprom}` | {esc(f.label)} | {typ} | {esc(f.unit)} | {f.confidence} | "
              f"{esc(desc)} | {esc(f.evidence)} | {esc(f.observed)} | {esc(schema_cell(f))} |")


if __name__ == "__main__":
    main()
