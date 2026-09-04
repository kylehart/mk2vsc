"""E2: an assistant on one inverter of a pair (cross-flow)."""
from __future__ import annotations

from typing import List

from . import Rule
from ..context import FileContext
from ..report import Finding, DEVICE_CONFIRMED
from .e1 import TEXT


def run(ctx: FileContext) -> List[Finding]:
    if len(ctx.serials) < 2:
        return []
    kinds = {s: ctx.assistant[s]["kind"] for s in ctx.serials}
    has = [s for s, k in kinds.items() if k == "records"]
    lacks = [s for s, k in kinds.items() if k != "records"]
    if not has or not lacks:
        return []
    ev = [{"serial": s, "field": "assistant_area", "label": "assistant area", "unit": "", "raw": ctx.assistant[s]["tail_hex"],
           "value": ctx.assistant[s]["summary"], "schema_min": None, "schema_max": None, "schema_default": None,
           "confidence": "CONFIRMED", "vote": "has assistant" if s in has else "no assistant"} for s in ctx.serials]
    return [Finding(id="E2", rule="E2", title="Assistant on one inverter of the pair", severity="BLOCKS",
                    decode_confidence="CONFIRMED", evidence_class=DEVICE_CONFIRMED, serials=list(ctx.serials), evidence=ev,
                    conditional=["ess_intended"],
                    message=f"{', '.join(has)} carries an assistant; {', '.join(lacks)} does not. With ESS on one inverter of a "
                            f"parallel pair the two run different control laws on one battery (observed on System C, "
                            f"2026-07-20: cross-flow between the units). {TEXT}",
                    fix={"kind": "gui", "text": TEXT, "lacks": lacks})]


RULE = Rule("E2", "Assistant on one inverter of the pair", DEVICE_CONFIRMED,
            "Assistant records on one block and none on the other. Observed on System C from 2026-07-17 to 07-20. "
            "Conditional on whether ESS is intended.",
            "system_c/system_c_2026-07-20_download_half-ess_deviceform_1.rvms", run)
