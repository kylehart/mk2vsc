"""Inverter parity: do the two blocks of a pair agree where they must?

Why this exists
---------------
The two inverters of a parallel or split-phase pair are two halves of one machine: one DC bus, one
battery, one synchronised AC reference.  Victron's parallel/split-phase manual requires the units to
be the same type, size, system voltage, feature set and firmware, and states plainly that when they
disagree the numbers shown on the GX device and VRM "will or can be wrong" and controlling the
system "will not always work properly either".

It is NOT a rule that the two blocks are byte-identical.  The same manual names settings that are
configured PER UNIT, and those legitimately differ:

  * Virtual Switch      "A unique virtual switch configuration can be configured for each unit"
  * Assistants          "genset start/stop, relay locker etcetera, a unique configuration can be
                         made in each unit"
  * Grid code           "Country / grid code standard and other grid related values" are set in
                         each unit
  * DC low shutdown     each unit carries its own "DC input low shut-down values"

So the rule is: parity everywhere OUTSIDE that documented exception list.  A difference inside it is
expected and says nothing; a difference outside it is a finding.

Why an exception and not a warning string
-----------------------------------------
A disagreement changes what a calling program should do -- it is not decoration on a report.  A
caller that does not want to handle it should not silently proceed past it.  So the eager entry
point RAISES :class:`ParityMismatch`, and a caller must either catch it or deliberately ask for the
report form instead.  ``docs/SAFETY.md`` describes the same reasoning for refusing locked writes.

Two honest limits:

* **We do not decode every setting.**  Parity is computed over the raw 16-bit words, so a
  disagreement is reported whether or not we have a name for the field.  Not having labelled a
  setting is not a reason to stay quiet about the two inverters disagreeing on it.
* **"Expected" is not "correct".**  A grid-code difference is expected per Victron's documentation.
  This module does not claim the value itself is right.
"""

from dataclasses import dataclass, field as _dc_field
from typing import Dict, List, Optional, Sequence, Tuple

from .fields import FIELDS, GRID_CODE_LOCKED, lookup
from .sections import RvmsFile
from .units import UnitBlock, unit_blocks

__all__ = [
    "ParityMismatch",
    "ParityDifference",
    "ParityReport",
    "EXPECTED_PER_UNIT",
    "check_parity",
    "check_parity_bytes",
    "parity_report_bytes",
]

#: Settings Victron documents as configured per unit, so a difference is EXPECTED.
#: Grid code is 81 and 128-191 (``GRID_CODE_LOCKED`` already carries exactly that set).
#: Virtual Switch registers are listed explicitly rather than by name prefix so the set is auditable.
VIRTUAL_SWITCH_IDS = frozenset(
    {15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33,
     34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 52, 53, 54, 55, 56, 57, 58, 59, 70}
)

#: DC input low shut-down values, named per unit in the manual.
DC_LOW_SHUTDOWN_IDS = frozenset({11, 12})

EXPECTED_PER_UNIT = frozenset(GRID_CODE_LOCKED) | VIRTUAL_SWITCH_IDS | DC_LOW_SHUTDOWN_IDS

#: Differences here are treated as a probable commissioning error rather than a configuration
#: choice: both inverters act on ONE shared battery, so two different targets is not a tuning.
SHARED_BATTERY_IDS = frozenset({2, 3, 4, 5, 6, 7, 8, 9, 64, 65, 72, 74})


@dataclass(frozen=True)
class ParityDifference:
    """One setting on which the pair disagrees."""

    setting_id: int
    name: Optional[str]          # None when we have no label for this register
    values: Dict[str, int]       # serial -> raw 16-bit word
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
    """The result of comparing a pair.  ``ok`` is False when anything unexpected differs."""

    serials: List[str] = _dc_field(default_factory=list)
    differences: List[ParityDifference] = _dc_field(default_factory=list)
    checked: int = 0
    comparable: bool = True      # False when the file does not hold a comparable pair
    reason: str = ""             # why it is not comparable

    @property
    def unexpected(self) -> List[ParityDifference]:
        return [d for d in self.differences if not d.expected]

    @property
    def errors(self) -> List[ParityDifference]:
        return [d for d in self.differences if d.severity == "error"]

    @property
    def ok(self) -> bool:
        return not self.unexpected

    def render(self) -> str:
        if not self.comparable:
            return f"parity: not checked -- {self.reason}"
        if not self.differences:
            return f"parity OK: {' vs '.join(self.serials)} agree on all {self.checked} settings"
        lines = [f"parity: {' vs '.join(self.serials)}, {self.checked} settings compared"]
        for d in sorted(self.differences, key=lambda x: (x.expected, -int(x.shared_battery), x.setting_id)):
            mark = {"error": "FAIL", "warning": "WARN", "expected": "note"}[d.severity]
            lines.append(f"  {mark}  {d.describe()}")
        return "\n".join(lines)


class ParityMismatch(RuntimeError):
    """Raised when the two inverters disagree outside the documented per-unit exception list.

    Carries the full :class:`ParityReport` as ``.report`` so a caller that catches it can decide
    what to do without re-reading the file.
    """

    def __init__(self, report: ParityReport):
        self.report = report
        n = len(report.unexpected)
        worst = "commissioning error" if report.errors else "difference"
        super().__init__(
            f"inverters disagree on {n} setting{'s' if n != 1 else ''} "
            f"outside the documented per-unit list ({worst}); "
            f"see .report for detail:\n{report.render()}"
        )


def _blocks(data: bytes) -> List[UnitBlock]:
    return list(unit_blocks(RvmsFile.parse(data)))


def parity_report_bytes(data: bytes) -> ParityReport:
    """Compare the pair and RETURN a report.  Never raises for a mismatch."""
    rep = ParityReport()
    try:
        blocks = _blocks(data)
    except Exception as exc:                                  # pragma: no cover - parse guarded above
        rep.comparable = False
        rep.reason = f"file could not be parsed ({exc})"
        return rep

    if len(blocks) < 2:
        rep.comparable = False
        rep.reason = f"only {len(blocks)} inverter block(s); parity needs a pair"
        return rep
    if len(blocks) > 2:
        rep.comparable = False
        rep.reason = f"{len(blocks)} inverter blocks; this check handles pairs only"
        return rep

    a, b = blocks
    rep.serials = [a.serial, b.serial]
    by_id = {f.id: f for f in FIELDS}

    for sid in range(192):
        try:
            va, vb = a.setting(sid), b.setting(sid)
        except (IndexError, ValueError):
            continue
        rep.checked += 1
        if va == vb:
            continue
        fld = by_id.get(sid)
        decoded: Dict[str, object] = {}
        if fld is not None:
            try:
                decoded = {a.serial: fld.decode(va), b.serial: fld.decode(vb)}
            except Exception:
                decoded = {}
        rep.differences.append(
            ParityDifference(
                setting_id=sid,
                name=fld.name if fld is not None else None,
                values={a.serial: va, b.serial: vb},
                decoded=decoded,
                expected=sid in EXPECTED_PER_UNIT,
                shared_battery=sid in SHARED_BATTERY_IDS,
            )
        )
    return rep


def check_parity_bytes(data: bytes, *, raise_on_mismatch: bool = True) -> ParityReport:
    """Eager parity check.  Raises :class:`ParityMismatch` unless told not to."""
    rep = parity_report_bytes(data)
    if raise_on_mismatch and rep.comparable and not rep.ok:
        raise ParityMismatch(rep)
    return rep


def check_parity(path: str, *, raise_on_mismatch: bool = True) -> ParityReport:
    with open(path, "rb") as fh:
        return check_parity_bytes(fh.read(), raise_on_mismatch=raise_on_mismatch)
