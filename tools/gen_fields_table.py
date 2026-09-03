#!/usr/bin/env python3
"""Print the settings table in docs/FIELDS.md as Markdown, generated from rvms/fields.py.

    PYTHONPATH=. python3 tools/gen_fields_table.py > /tmp/fields_table.md

The table in docs/FIELDS.md is pasted from this output so the document cannot drift from the code.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvms.fields import FIELDS  # noqa: E402


def esc(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def main():
    print("| ID | Offset | Name | VEConfigure label | Type / scale | Unit | Confidence | Presumed usage | Evidence | Observed values |")
    print("|---:|:------:|------|-------------------|--------------|------|:----------:|----------------|----------|-----------------|")
    for f in FIELDS:
        typ = "u16 bitmask" if f.bits else ("u16 / %g" % f.scale if f.scale != 1 else "u16")
        desc = f.description
        if f.bits:
            desc += " Bits: " + "; ".join(f"bit {b} = {m}" for b, m in sorted(f.bits.items())) + "."
        print(f"| {f.id} | +0x{f.offset:03x} | `{f.name}` | {esc(f.label)} | {typ} | {esc(f.unit)} | {f.confidence} | "
              f"{esc(desc)} | {esc(f.evidence)} | {esc(f.observed)} |")


if __name__ == "__main__":
    main()
