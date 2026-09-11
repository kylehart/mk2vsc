"""Inverter parity: do the inverters of a VE.Bus system agree where they must?

Why this exists
---------------
The inverters of a parallel, split-phase or three-phase system are parts of one machine: one DC
bus, one battery, one synchronised AC reference.  Victron's parallel/split-phase manual requires the
units to be the same type, size, system voltage, feature set and firmware, and states plainly that
when they disagree the numbers shown on the GX device and VRM "will or can be wrong" and controlling
the system "will not always work properly either".

It is NOT a rule that the blocks are byte-identical.  The same manual names settings that are
configured PER UNIT, and those legitimately differ:

  * Virtual Switch      "A unique virtual switch configuration can be configured for each unit"
  * Assistants          "genset start/stop, relay locker etcetera, a unique configuration can be
                         made in each unit"
  * Grid code           "Country / grid code standard and other grid related values" are set in
                         each unit
  * DC low shutdown     each unit carries its own "DC input low shut-down values"

So the rule is: parity everywhere OUTSIDE that documented exception list.  A difference inside it is
expected and says nothing; a difference outside it is a finding.

Firmware is checked too, and separately: the units must run the same version, and settings can agree
word for word while the versions differ.  That is a block-header property rather than a numbered
register, so it is reported on its own and also fails the eager check.

Why an exception and not a warning string
-----------------------------------------
A disagreement changes what a calling program should do -- it is not decoration on a report.  A
caller that does not want to handle it should not silently proceed past it.  So the eager entry
point RAISES: :class:`ParityMismatch` when the units disagree outside the exception list, and
:class:`ParityNotComparable` when the file cannot be judged at all (fewer than two inverter blocks,
a block too short to hold its settings array, duplicate serials).  Silence on an input the check
could not examine would be the exact failure this module exists to prevent.  A caller that wants
the report regardless asks for :func:`parity_report_bytes`, which never raises.

Two-inverter pairs vs. three-phase systems
------------------------------------------
The comparison is written for N >= 2 blocks so that a three-phase file is checked rather than
refused: every setting is compared across all units, and a difference is reported with every
unit's value.  **Only pairs have been exercised against real hardware.**  Every fixture in this
repository holds exactly two inverter blocks, and no three-phase system has been read, written or
verified with this tool.  For N > 2 the exception list is assumed to hold unchanged (it is a
property of the setting, not of the unit count), but that is an assumption, not an observation.
Treat N > 2 as unsupported: the code path exists so it fails loudly rather than silently, and the
tests cover it only with synthetic files built by duplicating a real block.

Honest limits
-------------
* **We do not decode every setting.**  Parity is computed over the raw 16-bit words, so a
  disagreement is reported whether or not we have a name for the field.  Not having labelled a
  setting is not a reason to stay quiet about the units disagreeing on it.
* **"Expected" is not "correct".**  A grid-code difference is expected per Victron's documentation.
  This module does not claim the value itself is right.
* **Virtual Switch bits also live in flag words.**  Settings 1, 60 and 62 carry VS-related bits
  alongside unrelated ones.  Those words are NOT on the exception list, so a legitimately per-unit
  VS configuration that differs only there is reported as a ``warning``.  The exception list is
  by whole register, deliberately: excusing a whole flag word would also excuse its non-VS bits.
"""

from dataclasses import dataclass, field as _dc_field
from typing import Dict, List, Optional

from .fields import FIELDS, GRID_CODE_LOCKED
from .sections import RvmsFile
from .units import N_SETTINGS, UnitBlock, unit_blocks

#: bytes of section checksum that trail every block's payload inside ``UnitBlock.raw``
CHECKSUM_BYTES = 4

__all__ = [
    "ParityMismatch",
    "ParityNotComparable",
    "ParityDifference",
    "ParityReport",
    "EXPECTED_PER_UNIT",
    "SHARED_BATTERY_IDS",
    "VIRTUAL_SWITCH_IDS",
    "DC_LOW_SHUTDOWN_IDS",
    "check_parity",
    "check_parity_bytes",
    "parity_report_bytes",
]

#: Settings Victron documents as configured per unit, so a difference is EXPECTED.
#: Grid code is 81 and 128-191 (``GRID_CODE_LOCKED`` already carries exactly that set).
#: Virtual Switch registers are listed explicitly rather than by name prefix so the set is auditable
#: (tests assert it against the ``vs_`` fields in ``fields.py``).
VIRTUAL_SWITCH_IDS = frozenset(
    {15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33,
     34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 52, 53, 54, 55, 56, 57, 58, 59, 70}
)

#: DC input low shut-down values, named per unit in the manual.
DC_LOW_SHUTDOWN_IDS = frozenset({11, 12})

EXPECTED_PER_UNIT = frozenset(GRID_CODE_LOCKED) | VIRTUAL_SWITCH_IDS | DC_LOW_SHUTDOWN_IDS

#: Differences here are treated as a probable commissioning error rather than a configuration
#: choice: every inverter acts on ONE shared battery, so two different targets is not a tuning.
SHARED_BATTERY_IDS = frozenset({2, 3, 4, 5, 6, 7, 8, 9, 64, 65, 72, 74})


@dataclass(frozen=True)
class ParityDifference:
    """One setting on which the units disagree."""

    setting_id: int
    name: Optional[str]          # None when we have no label for this register
    values: Dict[str, int]       # serial -> raw 16-bit word, one entry per unit
    decoded: Dict[str, object]   # serial -> decoded value, empty when undecodable
    expected: bool               # documented per-unit (grid code / VS / DC low shutdown)
    shared_battery: bool         # acts on the shared battery: a probable commissioning error

    @property
    def severity(self) -> str:
        if self.expected:
            return "expected"
        return "error" if self.shared_battery else "warning"

    def describe(self) -> str:
        who = ", ".join(f"{s}={self.decoded.get(s, self.values[s])}" for s in sorted(self.values))
        label = self.name or f"setting {self.setting_id} (unnamed)"
        if self.expected:
            return f"{label}: differs ({who}) -- documented per-unit, expected"
        if self.shared_battery:
            return (f"{label}: inverters DISAGREE ({who}) -- acts on the SHARED battery; "
                    f"probable commissioning error")
        return f"{label}: inverters differ ({who}) -- not a documented per-unit setting"


@dataclass
class ParityReport:
    """The result of comparing the units.

    ``ok`` is True only when the file was comparable AND nothing unexpected differs.  A report
    that could not compare anything is never ``ok``: silence is not agreement.
    """

    serials: List[str] = _dc_field(default_factory=list)
    differences: List[ParityDifference] = _dc_field(default_factory=list)
    checked: int = 0
    comparable: bool = True      # False when the file does not hold a comparable set of blocks
    reason: str = ""             # why it is not comparable
    firmware: Dict[str, int] = _dc_field(default_factory=dict)   # serial -> version, ONLY when they disagree

    @property
    def unexpected(self) -> List[ParityDifference]:
        return [d for d in self.differences if not d.expected]

    @property
    def errors(self) -> List[ParityDifference]:
        return [d for d in self.differences if d.severity == "error"]

    @property
    def firmware_disagrees(self) -> bool:
        return bool(self.firmware)

    @property
    def ok(self) -> bool:
        return self.comparable and not self.unexpected and not self.firmware_disagrees

    @property
    def units(self) -> int:
        return len(self.serials)

    def render(self) -> str:
        if not self.comparable:
            return f"parity: NOT CHECKED -- {self.reason}"
        head = " vs ".join(self.serials)
        note = "" if self.units == 2 else f"  [{self.units} units: beyond a pair is untested, see docs/PARITY.md]"
        fw = ""
        if self.firmware_disagrees:
            who = ", ".join(f"{s}={self.firmware[s]}" for s in sorted(self.firmware))
            fw = f"\n  FAIL  firmware: units DISAGREE ({who}) -- every unit must run the same firmware"
        if not self.differences:
            if fw:
                return f"parity: {head}, {self.checked} settings agree{note}{fw}"
            return f"parity OK: {head} agree on all {self.checked} settings{note}"
        lines = [f"parity: {head}, {self.checked} settings compared{note}"]
        for d in sorted(self.differences, key=lambda x: (x.expected, -int(x.shared_battery), x.setting_id)):
            mark = {"error": "FAIL", "warning": "WARN", "expected": "note"}[d.severity]
            lines.append(f"  {mark}  {d.describe()}")
        return "\n".join(lines) + fw


class ParityMismatch(RuntimeError):
    """Raised when the units disagree outside the documented per-unit exception list.

    Carries the full :class:`ParityReport` as ``.report`` so a caller that catches it can decide
    what to do without re-reading the file.
    """

    def __init__(self, report: ParityReport):
        self.report = report
        n = len(report.unexpected)
        if n:
            worst = "commissioning error" if report.errors else "difference"
            head = (f"inverters disagree on {n} setting{'s' if n != 1 else ''} "
                    f"outside the documented per-unit list ({worst})")
            if report.firmware_disagrees:
                head += " and are on different firmware"
        else:
            head = "inverters are on different firmware versions"
        super().__init__(f"{head}; see .report for detail:\n{report.render()}")


class ParityNotComparable(RuntimeError):
    """Raised when parity could not be judged at all, so that not-checked is never mistaken for OK.

    Fewer than two inverter blocks, a block too short to hold its settings array, or duplicate
    serials.  ``.report`` carries the reason.
    """

    def __init__(self, report: ParityReport):
        self.report = report
        super().__init__(f"parity not comparable: {report.reason}")


def parity_report_bytes(data: bytes) -> ParityReport:
    """Compare every inverter block and RETURN a report.  Never raises for a mismatch.

    Parse errors are reported as ``comparable=False`` rather than raised, so a display command can
    always print something; use :func:`check_parity_bytes` when silence must be impossible.
    """
    rep = ParityReport()
    try:
        blocks: List[UnitBlock] = list(unit_blocks(RvmsFile.parse(data)))
    except Exception as exc:
        rep.comparable = False
        rep.reason = f"file could not be parsed ({exc})"
        return rep

    if len(blocks) < 2:
        rep.comparable = False
        rep.reason = f"only {len(blocks)} inverter block(s); parity needs at least two"
        return rep

    # Fail closed on a block that cannot hold the whole settings array: comparing a partial array
    # and reporting "OK" would be silence dressed as agreement.  (RvmsFile.parse accepts a section
    # with only its pointer and checksum, so this is reachable on a damaged file.)
    for b in blocks:
        # +4 reserves the section's checksum trailer, which is part of ``raw``.  Without it a block
        # short by up to four bytes passes this guard and the last reads interpret checksum bytes as
        # settings 190 and 191 -- and because those ids are on the per-unit exception list, two
        # equally damaged blocks could report ok=True.  Silence dressed as agreement is the one
        # outcome this module exists to prevent.
        need = b.settings_offset + 2 * N_SETTINGS + CHECKSUM_BYTES
        if len(b.raw) < need:
            rep.comparable = False
            rep.reason = (f"block {b.index} ({b.serial}) is {len(b.raw)} bytes; "
                          f"{need} needed to hold all {N_SETTINGS} settings before the checksum")
            return rep

    serials = [b.serial for b in blocks]
    if len(set(serials)) != len(serials):
        rep.comparable = False
        rep.reason = f"duplicate inverter serial in file: {serials}"
        return rep

    rep.serials = serials

    # Victron requires every unit to run the same firmware version.  Settings can agree word for word
    # while the units are on different firmware, so a settings-only comparison would report parity OK
    # on a system the manual says is misconfigured.  This is a property of the block header, not of a
    # numbered register, so it is reported separately from the 192-register comparison.
    firmwares = {b.serial: b.firmware_version for b in blocks}
    if len(set(firmwares.values())) > 1:
        rep.firmware = firmwares

    by_id = {f.id: f for f in FIELDS}

    for sid in range(N_SETTINGS):
        values = {b.serial: b.setting(sid) for b in blocks}
        rep.checked += 1
        if len(set(values.values())) == 1:
            continue
        fld = by_id.get(sid)
        decoded: Dict[str, object] = {}
        if fld is not None:
            try:
                decoded = {s: fld.decode(v) for s, v in values.items()}
            except Exception:
                decoded = {}
        rep.differences.append(
            ParityDifference(
                setting_id=sid,
                name=fld.name if fld is not None else None,
                values=values,
                decoded=decoded,
                expected=sid in EXPECTED_PER_UNIT,
                shared_battery=sid in SHARED_BATTERY_IDS,
            )
        )
    return rep


def check_parity_bytes(data: bytes, *, raise_on_mismatch: bool = True) -> ParityReport:
    """Eager parity check.

    Raises :class:`ParityNotComparable` when the file cannot be judged and :class:`ParityMismatch`
    when the units disagree outside the documented per-unit list.  ``raise_on_mismatch=False``
    turns both raises off and returns the report for the caller to inspect.
    """
    rep = parity_report_bytes(data)
    if raise_on_mismatch:
        if not rep.comparable:
            raise ParityNotComparable(rep)
        if not rep.ok:
            raise ParityMismatch(rep)
    return rep


def check_parity(path: str, *, raise_on_mismatch: bool = True) -> ParityReport:
    with open(path, "rb") as fh:
        return check_parity_bytes(fh.read(), raise_on_mismatch=raise_on_mismatch)
