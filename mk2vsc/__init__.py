"""
rvms -- read, verify, edit and diff Victron VEConfigure ``.rvms`` configuration files without VEConfigure.

Zero dependencies. Python 3.9+.

Quick tour::

    from mk2vsc import RvmsFile, units_by_serial, decode_file, set_settings, diff_files

    f = RvmsFile.load("system.rvms")
    f.all_checksums_ok                      # every section's integrity trailer validates
    units_by_serial(f)["HQ2414U6FVN"].setting(2) / 100   # absorption voltage

Safety model in one paragraph: this library produces *files*.  It never talks to an inverter.  A valid
file is necessary, not sufficient: editing the right offset is on you (see ``fields.py`` confidence
levels), and the only proven-safe edits are length-preserving value changes to the settings array.
Adding, removing or transplanting an assistant (ESS etc.) by file has never worked for us and has
disrupted live systems.  Read docs/SAFETY.md before uploading anything.
"""
from .sections import RvmsFile, Section, RvmsParseError, sum32_le, scan_unit_blocks
from .units import UnitBlock, unit_blocks, units_by_serial
from .fields import FIELDS, BY_ID, BY_NAME, lookup, Field
from .decode import decode_file, decode_bytes
from .writer import set_settings, WriteRefused
from .diff import diff_files, diff_bytes
from .qualify import qualify_file, Intent

__version__ = "0.1.0"
__all__ = [
    "RvmsFile", "Section", "RvmsParseError", "sum32_le", "scan_unit_blocks",
    "UnitBlock", "unit_blocks", "units_by_serial",
    "FIELDS", "BY_ID", "BY_NAME", "lookup", "Field",
    "decode_file", "decode_bytes", "set_settings", "WriteRefused", "diff_files", "diff_bytes",
    "qualify_file", "Intent",
]
