"""
mk2vsc: read, verify, edit and diff Victron VEConfigure ``.rvms`` configuration files without VEConfigure.

Zero dependencies. Python 3.9+.

Quick tour::

    import mk2vsc
    cfg = mk2vsc.load("download.rvms")
    cfg.serials                            # ["HQ0000A0002", "HQ0000A0001"]
    cfg["HQ0000A0001"]["absorption"]       # 56.0 (volts)
    cfg.set("absorption", 56.8)            # every inverter (a shared battery wants them equal)
    path = cfg.save()                      # download.edited.rvms; the input is never overwritten
    # upload `path` through VRM Remote VEConfigure, download again, then:
    ok, report = mk2vsc.verify(path, "redownload.rvms")

The facade (``mk2vsc.api``) is a thin layer over the same modules the CLI uses: ``sections`` (file
grammar and checksums), ``units`` (per-inverter block), ``fields`` (the settings table with confidence
levels), ``schema`` (the device's own setting ranges), ``align`` and ``limits`` (block alignment, range edges), ``ui``
(VEConfigure tab placement), ``writer`` (guarded edits), ``diff``, ``qualify``, ``assistants`` (read-only parsing),
``assistant`` (remove / reinstall), ``upload_form``, ``history``, ``census`` and ``diagnose`` (findings with evidence).
``verify_bytes``, ``census_text`` and ``history.snapshots_from_bytes`` take bytes for callers that hold files in memory.

Safety model in one paragraph: this library produces *files*.  It never talks to an inverter.  A valid
file is necessary, not sufficient: editing the right offset is on you (see ``fields.py`` confidence
levels), and the only proven-safe edits are length-preserving value changes to the settings array.
Removing an assistant, or reinstalling one from an earlier download of the same system, works through
``mk2vsc.assistant`` (upload-form files; uploading them resets the VE.Bus).  Installing an assistant on a
system that never had one is unproven (``mk2vsc.experimental``).  Read docs/SAFETY.md before uploading anything.
"""
from .sections import RvmsFile, Section, RvmsParseError, sum32_le, scan_unit_blocks
from .units import UnitBlock, unit_blocks, units_by_serial
from .fields import FIELDS, BY_ID, BY_NAME, ALIASES, lookup, Field
from .decode import decode_file, decode_bytes
from .writer import set_settings, set_bits, WriteRefused
from .diff import diff_files, diff_bytes
from .qualify import qualify_file, Intent
from .api import load, loads, verify, verify_bytes, Config, Unit
from .census import census_text

__version__ = "0.10.0"
__all__ = [
    "load", "loads", "verify", "verify_bytes", "census_text", "Config", "Unit",
    "RvmsFile", "Section", "RvmsParseError", "sum32_le", "scan_unit_blocks",
    "UnitBlock", "unit_blocks", "units_by_serial",
    "FIELDS", "BY_ID", "BY_NAME", "ALIASES", "lookup", "Field",
    "decode_file", "decode_bytes", "set_settings", "set_bits", "WriteRefused", "diff_files", "diff_bytes",
    "qualify_file", "Intent",
]
