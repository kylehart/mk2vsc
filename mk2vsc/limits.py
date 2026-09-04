"""
Settings sitting at the edge of their own allowed range.

A charger voltage typed as the lowest value VEConfigure will accept is a recognisable mistake: the
schema says absorption may be 48.00 to 64.00 V, the default is 57.60 V, and a file carrying exactly
48.00 V on both absorption and float was almost certainly commissioned wrong.  The device's own
schema (``BareSettingInfo``) gives every setting's min, max and default, so this check needs no
table of our own.

The rule is deliberately narrow.  On the fixture corpus (170 inverter blocks) a naive "raw == min or
raw == max" fires on every block: a dozen Virtual Switch timers default to 0 (their minimum), charge
current defaults to its maximum, and the grid-code slots are 0xffff.  Requiring all of the following
leaves exactly the mis-commissioned blocks:

* the setting has a physical unit (V, A, Ah, Hz), so enums, timers and flag words are excluded;
* our confidence in the decode is CONFIRMED or HIGH;
* the value sits at the schema minimum or maximum;
* that limit is *not* the schema default (a default at the limit is the normal state, not a symptom).

Heuristic after talas9/rvsc-tools, whose viewer marks charger setpoints "at minimum of allowed range".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .fields import FIELDS, CONFIRMED, HIGH, Field
from .schema import SettingInfo
from .units import UnitBlock, N_SETTINGS

PHYSICAL_UNITS = {"V", "A", "Ah", "Hz"}


@dataclass(frozen=True)
class LimitHit:
    field: Field
    raw: int
    edge: str           # "minimum" or "maximum"
    default_raw: int

    @property
    def value(self) -> float:
        return self.field.decode(self.raw)

    @property
    def default(self) -> float:
        return self.field.decode(self.default_raw)

    @property
    def message(self) -> str:
        v, d = self.value, self.default
        vs = f"{v:g}" if isinstance(v, float) else str(v)
        ds = f"{d:g}" if isinstance(d, float) else str(d)
        return f"at {self.edge} of allowed range ({vs} {self.field.unit}; default {ds} {self.field.unit})"


def at_limits(u: UnitBlock, schema: List[SettingInfo]) -> List[LimitHit]:
    """Physical settings of this block that sit at their schema min or max, when that limit is not the
    default.  Empty on a normally commissioned file."""
    out: List[LimitHit] = []
    by_id = {r.id: r for r in schema}
    for f in FIELDS:
        if f.id >= N_SETTINGS or f.bits or f.unit not in PHYSICAL_UNITS or f.confidence not in (CONFIRMED, HIGH):
            continue
        r = by_id.get(f.id)
        if r is None or r.unused or r.min == r.max:
            continue
        raw = u.setting(f.id)
        if raw == r.min and r.default != r.min:
            out.append(LimitHit(f, raw, "minimum", r.default))
        elif raw == r.max and r.default != r.max:
            out.append(LimitHit(f, raw, "maximum", r.default))
    return out
