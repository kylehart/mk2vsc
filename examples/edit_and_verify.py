#!/usr/bin/env python3
"""
The whole loop from Python, on a fixture: read, edit, save next to the input, check, and verify against
the device's real re-download of that same change (2026-07-20, Guava).

    python examples/edit_and_verify.py
"""
import os
import shutil
import tempfile

import mk2vsc

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "..", "fixtures", "guava")
DOWNLOAD = os.path.join(FIX, "guava_2026-07-20_download_bare_deviceform_1.rvms")
REDOWNLOAD = os.path.join(FIX, "guava_2026-07-20_download_bare_deviceform_2.rvms")

with tempfile.TemporaryDirectory() as td:
    src = os.path.join(td, "download.rvms")
    shutil.copyfile(DOWNLOAD, src)

    cfg = mk2vsc.load(src)
    print(cfg.summary())
    print()
    for e in cfg.set_many({"absorption": 56.8, "float": 54.0}):
        d = e.as_dict()
        print(f"{d['serial']} {d['field']}: {d['old']} -> {d['new']} {d['unit']}")
    out = cfg.save()
    print("wrote", out)

    ok, results = cfg.check(absorption=56.8, float=54.0)
    print("check:", "QUALIFIED" if ok else "NOT QUALIFIED")
    for level, msg in results:
        print(f"  {level:4s} {msg}")

    ok, report = mk2vsc.verify(out, REDOWNLOAD)
    print(report)
