#!/usr/bin/env python3
"""
Edit a device download with the library API, then verify the result the way the change-control
loop does: diff against the input and qualify against an intent file.

    python examples/edit_and_verify.py [input.rvms] [intent.json]

Defaults to a fixture from the corpus.  Nothing is uploaded; the output goes to a temp file.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from mk2vsc import RvmsFile, units_by_serial, set_settings, diff_bytes, Intent  # noqa: E402
from mk2vsc.diff import render as render_diff  # noqa: E402
from mk2vsc.qualify import qualify_bytes, render as render_qual  # noqa: E402

src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, "..", "fixtures", "guava", "guava_2026-07-20_download_bare_deviceform_1.rvms")
intent_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "intent.example.json")

data = open(src, "rb").read()
f = RvmsFile.parse(data)
print(f"input: {src}\n  checksums ok: {f.all_checksums_ok}")
for serial, u in units_by_serial(f).items():
    print(f"  {serial}: absorption {u.setting(2) / 100} V, float {u.setting(3) / 100} V")

# serial=None applies the edit to every inverter (they share one battery).
out, edits = set_settings(data, [(None, "absorption_V", 56.8), (None, "float_V", 54.0)])
for e in edits:
    d = e.as_dict()
    print(f"  edit {d['serial']} {d['field']}: {d['old']} -> {d['new']} {d['unit']} at block {d['block_offset']}")

with tempfile.NamedTemporaryFile(suffix=".rvms", delete=False) as fh:
    fh.write(out)
    print(f"wrote {fh.name} ({len(out)} bytes, same length as input: {len(out) == len(data)})")

print("\ndiff input -> output (expect only the two settings plus checksums):")
print(render_diff(diff_bytes(data, out)))

intent = Intent(**json.load(open(intent_path))) if os.path.exists(intent_path) else Intent(settings={})
ok, results = qualify_bytes(out, intent)
print("\nqualification against", intent_path)
print(render_qual(ok, results, "output"))
