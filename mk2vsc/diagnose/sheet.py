"""The manual change sheet: VEConfigure tab › group › label, old value, new value, per inverter.  For anyone who
would rather type the change into the vendor tool than upload a file.  Placement comes from ``Field.ui``
(mk2vsc/ui.py); a field with no known placement prints "(tab unknown)" rather than a guess."""
from __future__ import annotations

from typing import List

from .report import FileReport
from ..fields import lookup
from ..ui import ui_for_bit

UNKNOWN_TAB = "(tab unknown)"


def _fmt(f, v) -> str:
    return f"{v:g} {f.unit}".strip() if isinstance(v, float) else f"{v} {f.unit}".strip()


def sheet_rows(report: FileReport, intent: dict) -> List[dict]:
    ctx = report._ctx
    rows = []
    for e in intent.get("edits", []):
        f = lookup(e["field"])
        ui = f.ui
        rows.append({"serial": e["serial"], "tab": ui.path if ui else UNKNOWN_TAB, "label": ui.label if ui else f.label,
                     "field": f.name, "old": _fmt(f, ctx.value(e["serial"], f.name)), "new": _fmt(f, e["value"])})
    for b in intent.get("bit_edits", []):
        f = lookup(b["field"])
        ui = ui_for_bit(f.id, b["bit"])
        name = (f.bits or {}).get(b["bit"], f"bit {b['bit']}")
        was = ctx.bit(b["serial"], f.name, b["bit"])
        tick = (lambda on: ("unticked" if on else "ticked") if (ui and ui.inverted) else ("ticked" if on else "unticked"))
        rows.append({"serial": b["serial"], "tab": ui.path if ui else UNKNOWN_TAB, "label": ui.label if ui else name,
                     "field": f"{f.name} bit {b['bit']}", "old": tick(was), "new": tick(b["set"])})
    return rows


def render_sheet(rows: List[dict]) -> str:
    if not rows:
        return "(no changes)"
    w = max(len(r["tab"]) for r in rows)
    lines = [f"{'inverter':12s} {'where in VEConfigure':{w}s}  {'field':38s} {'now':>14s}  ->  new"]
    for r in rows:
        lines.append(f"{r['serial']:12s} {r['tab']:{w}s}  {r['label']:38s} {r['old']:>14s}  ->  {r['new']}")
    return "\n".join(lines)
