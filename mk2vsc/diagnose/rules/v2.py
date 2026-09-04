"""V2: the Virtual Switch return threshold cannot be reached, so the system sticks in pass-through."""
from __future__ import annotations

from typing import List

from . import Rule
from ..context import FileContext
from ..report import Finding, INFERRED

IGNORE_AC_USAGES = {2, 3, 5, 6}     # vs_usage values that use the ignore-AC thresholds (fields.py setting 15)


def run(ctx: FileContext) -> List[Finding]:
    out = []
    for s in ctx.serials:
        if ctx.raw(s, "vs_usage") not in IGNORE_AC_USAGES or ctx.assistant[s]["kind"] == "records":
            continue                       # relay-only / generator / off: the return threshold is inert; or dead under an assistant (E4)
        ret, absorb = ctx.raw(s, "vs_accept_battery_above_V"), ctx.raw(s, "absorption_V")
        default = ctx.at_default(s, "vs_accept_battery_above_V")
        if ret < absorb and not default:
            continue
        why = "at the schema default" if default else "at or above the absorption voltage"
        ev = [ctx.evidence(s, "vs_accept_battery_above_V", why), ctx.evidence(s, "absorption_V", "the charger never exceeds this")]
        fix = {"kind": "values", "needs_value": [ctx.needs_value(s, "vs_accept_battery_above_V")], "edits": [], "bit_edits": []}
        out.append(Finding(id=f"V2:{s}", rule="V2", title="Virtual Switch return threshold unreachable", severity="FRAGILE",
                           decode_confidence=ev[0]["confidence"], evidence_class=INFERRED, serials=[s], evidence=ev, fix=fix,
                           message=f"{s}: the Virtual Switch accepts the AC input again above {ev[0]['value']:g} V, but the charger "
                                   f"never takes the battery above {ev[1]['value']:g} V, so once the input is ignored the system "
                                   f"stays in pass-through until something else intervenes. Enter a return voltage below "
                                   f"absorption (the fleet used 52.5 to 53.0 V on 48 V systems)."))
    return out


RULE = Rule("V2", "Virtual Switch return threshold unreachable", INFERRED,
            "vs_usage in an ignore-AC mode (2, 3, 5, 6), no assistant, and vs_accept_battery_above_V at or above absorption_V or at its schema default "
            "(64.00 V on the 48 V model). Inferred from fleet forensics: a 5.6-day pass-through episode with the return "
            "threshold at 64 V.",
            "system_c/system_c_2026-06-18_download_bare_deviceform_1.rvms", run)
