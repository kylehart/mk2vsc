"""C1: a physical setpoint at the edge of its own allowed range, when that edge is not the default.
A thin adapter over ``mk2vsc.limits.at_limits``."""
from __future__ import annotations

from typing import List

from . import Rule
from ..context import FileContext
from ..report import Finding, INFERRED
from ...limits import at_limits


def run(ctx: FileContext) -> List[Finding]:
    out = []
    for s in ctx.serials:
        for hit in at_limits(ctx.units[s], ctx.schema):
            ev = [ctx.evidence(s, hit.field.name, f"at the schema {hit.edge}, which is not the default")]
            fix = {"kind": "values", "needs_value": [ctx.needs_value(s, hit.field.name)], "edits": [], "bit_edits": []}
            out.append(Finding(id=f"C1:{s}:{hit.field.name}", rule="C1", title="Setpoint at the edge of its allowed range",
                               severity="DEGRADES", decode_confidence=hit.field.confidence, evidence_class=INFERRED,
                               serials=[s], evidence=ev, fix=fix,
                               message=f"{s}: {hit.field.name} is {hit.message}. A value typed as the extreme VEConfigure "
                                       f"accepts is a recognisable commissioning slip; enter the intended value."))
    return out


RULE = Rule("C1", "Setpoint at the edge of its allowed range", INFERRED,
            "mk2vsc.limits.at_limits(): a CONFIRMED/HIGH physical setting (V, A, Ah, Hz) at its schema minimum or maximum "
            "when that limit is not the default. Heuristic after talas9/rvsc-tools.",
            "system_c/system_c_2026-07-20_download_half-ess_deviceform_6.rvms", run)
