"""
mk2vsc: read, verify, edit and diff Victron VEConfigure ``.rvms`` configuration files without VEConfigure.

Zero dependencies. Python 3.9+.

Quick tour::

    import mk2vsc
    cfg = mk2vsc.load("download.rvms")
    cfg.serials                            # ["HQ2414AXENJ", "HQ2414U6FVN"]
    cfg["HQ2414U6FVN"]["absorption"]       # 56.0 (volts)
    cfg.set("absorption", 56.8)            # every inverter (a shared battery wants them equal)
    path = cfg.save()                      # download.edited.rvms; the input is never overwritten
    # upload `path` through VRM Remote VEConfigure, download again, then:
    ok, report = mk2vsc.verify(path, "redownload.rvms")

The facade (``mk2vsc.api``) is a thin layer over the same modules the CLI uses: ``sections`` (file
grammar and checksums), ``units`` (per-inverter block), ``fields`` (the settings table with confidence
levels), ``writer`` (guarded edits), ``diff``, ``qualify``, ``assistants`` (read-only), ``history``.

Safety model in one paragraph: this library produces *files*.  It never talks to an inverter.  A valid
file is necessary, not sufficient: editing the right offset is on you (see ``fields.py`` confidence
levels), and the only proven-safe edits are length-preserving value changes to the settings array.
Adding, removing or transplanting an assistant (ESS etc.) by file has never produced a running system for
us and has disrupted live systems.  Read docs/SAFETY.md before uploading anything.
"""
from .sections import RvmsFile, Section, RvmsParseError, sum32_le, scan_unit_blocks
from .units import UnitBlock, unit_blocks, units_by_serial
from .fields import FIELDS, BY_ID, BY_NAME, ALIASES, lookup, Field
from .decode import decode_file, decode_bytes
from .writer import set_settings, WriteRefused
from .diff import diff_files, diff_bytes
from .qualify import qualify_file, Intent
from .api import load, loads, verify, Config, Unit

__version__ = "0.2.1"
__all__ = [
    "load", "loads", "verify", "Config", "Unit",
    "RvmsFile", "Section", "RvmsParseError", "sum32_le", "scan_unit_blocks",
    "UnitBlock", "unit_blocks", "units_by_serial",
    "FIELDS", "BY_ID", "BY_NAME", "ALIASES", "lookup", "Field",
    "decode_file", "decode_bytes", "set_settings", "WriteRefused", "diff_files", "diff_bytes",
    "qualify_file", "Intent",
]
