#!/usr/bin/env python3
"""Print fixtures/manifest.json as a markdown table (used to build docs/FIXTURES.md)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
m = json.load(open(os.path.join(HERE, "..", "fixtures", "manifest.json")))
print("| file | bytes | state | form | origin | inverters (block length, flag) |")
print("|---|---:|---|---|---|---|")
for e in sorted(m["entries"], key=lambda e: e["file"]):
    blocks = ", ".join(f"{b['serial']} ({b['length']}, {b['flag']})" for b in e["blocks"])
    print(f"| {e['file']} | {e['size']} | {e['state']} | {e['form']} | {e['origin']} | {blocks} |")
