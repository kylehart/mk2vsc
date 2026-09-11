"""E2: an assistant on some inverters of a system but not others (cross-flow)."""
from __future__ import annotations

from typing import List

from . import Rule
from ..context import FileContext
from ..report import Finding, DEVICE_CONFIRMED
from .e1 import TEXT

REMOVE_TEXT = ("ESS not intended: complete the removal. `mk2vsc assistant remove` builds an upload-form file from a fresh download "
               "that removes the assistant from every inverter; uploading it resets the VE.Bus (docs/ASSISTANTS.md section 8). "
               "Otherwise remove it in VEConfigure.")

# `mk2vsc assistant` derives its upload-form transform from one two-inverter pair (docs/ASSISTANTS.md, mk2vsc/upload_form.py).
# On a system with more inverters the finding still holds -- the blocks disagree -- but the by-file remedy is untested there.
MULTI_UNIT_CAVEAT = (" This system has more than two inverters; `mk2vsc assistant` was derived from two-inverter systems and has "
                     "never run on one like yours, so treat VEConfigure as the remedy and report what you find.")


def run(ctx: FileContext) -> List[Finding]:
    kinds = {s: ctx.assistant[s]["kind"] for s in ctx.serials}
    has = [s for s, k in kinds.items() if k == "records"]
    lacks = [s for s, k in kinds.items() if k != "records"]
    if not has or not lacks:
        return []
    ev = [{"serial": s, "field": "assistant_area", "label": "assistant area", "unit": "", "raw": ctx.assistant[s]["tail_hex"],
           "value": ctx.assistant[s]["summary"], "schema_min": None, "schema_max": None, "schema_default": None,
           "confidence": "CONFIRMED", "vote": "has assistant" if s in has else "no assistant"} for s in ctx.serials]
    removing = ctx.ess_intended is False
    text = REMOVE_TEXT if removing else TEXT
    if len(ctx.serials) > 2:
        text += MULTI_UNIT_CAVEAT
    pair = len(ctx.serials) == 2
    return [Finding(id="E2", rule="E2", title="Assistant on some inverters but not others", severity="BLOCKS",
                    decode_confidence="CONFIRMED", evidence_class=DEVICE_CONFIRMED, serials=list(ctx.serials), evidence=ev,
                    conditional=[] if ctx.ess_intended is not None else ["ess_intended"],
                    message=f"{', '.join(has)} carries an assistant; {', '.join(lacks)} does not. With ESS on some inverters of "
                            f"{'a parallel pair' if pair else 'a system'} but not others they run different control laws on one "
                            f"battery (observed on System C, 2026-07-20: cross-flow between the units). {text}",
                    fix={"kind": "gui", "text": text, "lacks": lacks, "has": has, "remedy": "remove" if removing else "reinstall"})]


RULE = Rule("E2", "Assistant on some inverters but not others", DEVICE_CONFIRMED,
            "Assistant records on some blocks and not others. Observed on System C from 2026-07-17 to 07-20, a two-inverter "
            "system; on a system with more inverters the by-file remedy is untested and the message says so. "
            "Conditional on whether ESS is intended.",
            "system_c/system_c_2026-07-20_download_half-ess_deviceform_1.rvms", run, min_units=2)
