"""D1: lead-acid factory profile on a lithium bank."""
from __future__ import annotations

from typing import List, Optional

from . import Rule
from ..context import FileContext, LITHIUM_FIELD, LITHIUM_BIT, STORAGE_FIELD, STORAGE_BIT
from ..report import Finding, DEVICE_CONFIRMED, weakest

COPY_FIELDS = ["absorption_V", "float_V", "charge_characteristic", "dc_low_shutdown_V", "battery_capacity_Ah",
               "vs_accept_battery_above_V"]
VALUE_FIELDS = ["absorption_V", "float_V", "dc_low_shutdown_V"]


def votes(ctx: FileContext, s: str) -> List[dict]:
    """The lead-acid signature, one evidence record per vote.  Two or more votes make the finding."""
    out = []
    if not ctx.lithium_flag(s):
        out.append(ctx.evidence(s, LITHIUM_FIELD, "LithiumBattery flag clear"))
    for name in ("absorption_V", "float_V"):
        if ctx.at_min(s, name):
            out.append(ctx.evidence(s, name, "at the schema minimum"))
        elif ctx.at_default(s, name):
            out.append(ctx.evidence(s, name, "at the lead-acid schema default"))
    if ctx.bit(s, STORAGE_FIELD, STORAGE_BIT):
        out.append(ctx.evidence(s, STORAGE_FIELD, "bit 11 set (storage mode / adaptive per the two published readings)"))
    if ctx.raw(s, "charge_characteristic") == 3:
        out.append(ctx.evidence(s, "charge_characteristic", "curve 3 = adaptive + BatterySafe"))
    if ctx.at_default(s, "dc_low_shutdown_V"):
        out.append(ctx.evidence(s, "dc_low_shutdown_V", "at the schema default (the lead-acid floor)"))
    if ctx.raw(s, "battery_capacity_Ah") == 0:
        out.append(ctx.evidence(s, "battery_capacity_Ah", "0 Ah: battery monitor off"))
    if ctx.at_default(s, "vs_accept_battery_above_V"):
        out.append(ctx.evidence(s, "vs_accept_battery_above_V", "at the schema default (unreachable on a lithium bank)"))
    return out


def passes(ctx: FileContext, s: str) -> bool:
    return len(votes(ctx, s)) < 2


def healthy_peer(ctx: FileContext, s: str) -> Optional[str]:
    """Another inverter in the file that passes D1 and carries the lithium flag: the copy source."""
    for other in ctx.serials:
        if other != s and passes(ctx, other) and ctx.lithium_flag(other):
            return other
    return None


def run(ctx: FileContext) -> List[Finding]:
    if ctx.chemistry == "lead-acid":
        return []
    conditional = ["chemistry"] if ctx.chemistry == "unknown" else []
    out = []
    for s in ctx.serials:
        ev = votes(ctx, s)
        if len(ev) < 2:
            continue
        blocks = ctx.at_min(s, "absorption_V")
        sev = "BLOCKS" if blocks else "DEGRADES"
        peer = healthy_peer(ctx, s)
        bit_edits = [] if ctx.lithium_flag(s) else [{"serial": s, "field": LITHIUM_FIELD, "bit": LITHIUM_BIT, "set": True}]
        if peer:
            fields = [n for n in COPY_FIELDS if ctx.raw(s, n) != ctx.raw(peer, n)]
            fix = {"kind": "copy", "source": peer, "candidates": [peer], "targets": [s], "fields": fields, "bit_edits": bit_edits}
            how = f"copy the lithium profile from {peer} ({', '.join(fields)})"
        else:
            edits = [] if ctx.raw(s, "charge_characteristic") == 1 else [{"serial": s, "field": "charge_characteristic", "value": 1}]
            fix = {"kind": "values", "needs_value": [ctx.needs_value(s, n) for n in VALUE_FIELDS], "edits": edits, "bit_edits": bit_edits}
            how = "no healthy pair to copy from: enter absorption, float and low-voltage shutdown for this battery (decision 3: no generic template)"
        storage = ctx.bit(s, STORAGE_FIELD, STORAGE_BIT)
        a, fl = ctx.value(s, "absorption_V"), ctx.value(s, "float_V")
        msg = (f"{s}: {len(ev)} of 8 lead-acid signature votes. Absorption {a:g} V, float {fl:g} V"
               + (f" (schema minimum {ctx.info('absorption_V').decode(ctx.info('absorption_V').min):g} V: a lithium bank above that voltage is never charged)" if blocks else "")
               + f". Fix: {how}."
               + (" Storage mode (flags0 bit 11) stays set: that bit is not yet qualified for a by-file write; clear it in VEConfigure." if storage else ""))
        out.append(Finding(id=f"D1:{s}", rule="D1", title="Lead-acid factory profile on a lithium bank", severity=sev,
                           decode_confidence=weakest([e["confidence"] for e in ev]), evidence_class=DEVICE_CONFIRMED,
                           serials=[s], evidence=ev, message=msg, fix=fix, conditional=list(conditional)))
    return out


RULE = Rule("D1", "Lead-acid factory profile on a lithium bank", DEVICE_CONFIRMED,
            "Two or more of: LithiumBattery flag clear; absorption or float at the schema minimum or the lead-acid default; "
            "storage/adaptive bit set; charge curve 3; low-voltage shutdown at the schema default; capacity 0 Ah; VS return "
            "at the schema default. Gated on lithium chemistry (stated, or the flag on any inverter of the shared battery); "
            "conditional when the chemistry is unknown. Confirmed on hardware once (talas9, 24 V) and on three of eight "
            "fleet inverters.",
            "system_a/system_a_2026-07-20_download_bare_deviceform_1.rvms", run)
