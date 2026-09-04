"""V1: low-voltage shutdown left at the lead-acid default on a lithium bank."""
from __future__ import annotations

from typing import List

from . import Rule
from ..context import FileContext
from ..report import Finding, INFERRED


def run(ctx: FileContext) -> List[Finding]:
    if ctx.chemistry == "lead-acid":
        return []
    conditional = ["chemistry"] if ctx.chemistry == "unknown" else []
    out = []
    for s in ctx.serials:
        if not ctx.at_default(s, "dc_low_shutdown_V"):
            continue
        ev = [ctx.evidence(s, "dc_low_shutdown_V", "at the schema default")]
        v = ev[0]["value"]
        fix = {"kind": "values", "needs_value": [ctx.needs_value(s, "dc_low_shutdown_V")], "edits": [], "bit_edits": []}
        out.append(Finding(id=f"V1:{s}", rule="V1", title="Low-voltage shutdown at the lead-acid default", severity="FRAGILE",
                           decode_confidence=ev[0]["confidence"], evidence_class=INFERRED, serials=[s], evidence=ev, fix=fix,
                           conditional=list(conditional),
                           message=f"{s}: the inverter shuts down at {v:g} V, the lead-acid schema default. A lithium bank is "
                                   f"deeply discharged long before that; the BMS or the module low-voltage cut-off acts first, "
                                   f"and the inverter offers no floor of its own. Enter a floor for this battery (the fleet "
                                   f"used 48.0 to 48.5 V on 48 V systems)."))
    return out


RULE = Rule("V1", "Low-voltage shutdown at the lead-acid default", INFERRED,
            "dc_low_shutdown_V equals the file's schema default (37.20 V on the 48 V model) with lithium chemistry stated or "
            "inferred; conditional when unknown. Inferred from fleet forensics (voltage-based floor; a blackout at 48.5 V "
            "while SOC read 39 %).",
            "system_c/system_c_2026-06-18_download_bare_deviceform_1.rvms", run)
