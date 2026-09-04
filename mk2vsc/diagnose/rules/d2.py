"""D2: paired inverters disagree on a shared battery."""
from __future__ import annotations

from typing import List

from . import Rule
from .d1 import passes
from ..context import FileContext, LITHIUM_FIELD, LITHIUM_BIT
from ..report import Finding, DEVICE_CONFIRMED, weakest
from ...fields import FIELDS, CONFIRMED

CHARGER_FIELDS = [f.name for f in FIELDS if f.confidence == CONFIRMED and f.bits is None and f.id < 190]


def run(ctx: FileContext) -> List[Finding]:
    if len(ctx.serials) < 2:
        return []
    ev = []
    for name in CHARGER_FIELDS:
        raws = {s: ctx.raw(s, name) for s in ctx.serials}
        if len(set(raws.values())) > 1:
            ev += [ctx.evidence(s, name, "differs between the inverters") for s in ctx.serials]
    flags = {s: ctx.lithium_flag(s) for s in ctx.serials}
    if len(set(flags.values())) > 1:
        ev += [ctx.evidence(s, LITHIUM_FIELD, "LithiumBattery flag differs between the inverters") for s in ctx.serials]
    if not ev:
        return []
    fields = sorted({e["field"] for e in ev if e["field"] != LITHIUM_FIELD})
    passing = [s for s in ctx.serials if passes(ctx, s)]
    source = passing[0] if len(passing) == 1 else None
    targets = [s for s in ctx.serials if s != source] if source else list(ctx.serials)
    bit_edits = []
    if source and flags[source]:
        bit_edits = [{"serial": t, "field": LITHIUM_FIELD, "bit": LITHIUM_BIT, "set": True} for t in targets if not flags[t]]
    fix = {"kind": "copy", "source": source, "candidates": list(ctx.serials), "targets": targets, "fields": fields, "bit_edits": bit_edits}
    detail = "; ".join(f"{n}: " + ", ".join(f"{s}={ctx.value(s, n):g}" if isinstance(ctx.value(s, n), float) else f"{s}={ctx.value(s, n)}"
                                            for s in ctx.serials) for n in fields)
    if len(set(flags.values())) > 1:
        detail += "; LithiumBattery flag: " + ", ".join(f"{s}={'set' if v else 'clear'}" for s, v in flags.items())
    msg = (f"The inverters disagree on {detail}. On one shared battery these must match. "
           + (f"Source: {source} (the only block that passes D1); copying to {', '.join(targets)}."
              if source else "No automatic source: neither block passes D1 alone, or both do. Choose the source inverter yourself."))
    return [Finding(id="D2", rule="D2", title="Paired inverters disagree on a shared battery", severity="DEGRADES",
                    decode_confidence=weakest([e["confidence"] for e in ev]), evidence_class=DEVICE_CONFIRMED,
                    serials=list(ctx.serials), evidence=ev, message=msg, fix=fix, conditional=["shared_battery"])]


RULE = Rule("D2", "Paired inverters disagree on a shared battery", DEVICE_CONFIRMED,
            "Two blocks in one file with different values on a CONFIRMED file-settable charger field, or a different "
            "LithiumBattery flag (assistant-state mismatch is E2). The copy source is proposed only when exactly one "
            "block passes D1; otherwise the user chooses. Conditional on the inverters sharing one battery.",
            "system_a/system_a_2026-07-20_download_bare_deviceform_1.rvms", run)
