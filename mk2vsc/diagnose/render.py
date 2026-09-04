"""Plain-text rendering of a report: observations with evidence, never verdicts."""
from __future__ import annotations

from .report import Report, Finding
from ..fields import format_value


def _ev(e: dict) -> str:
    v = e["value"]
    is_flags = e["field"].startswith("flags")
    s = f"{e['field']} = 0x{v:04x} {e['unit']}" if is_flags and isinstance(v, int) else f"{e['field']} = {format_value(v, e['unit'])}"
    if e.get("schema_default") is not None and not is_flags:
        s += f" (schema {format_value(e['schema_min'])} to {format_value(e['schema_max'])}, default {format_value(e['schema_default'])})"
    if e.get("vote"):
        s += f": {e['vote']}"
    return s


def render_finding(f: Finding) -> str:
    head = f"  [{f.severity}] {f.rule} {f.title}  ({', '.join(f.serials)}; decode {f.decode_confidence}, evidence {f.evidence_class})"
    lines = [head]
    if f.conditional:
        lines.append(f"      conditional on: {', '.join(f.conditional)} (answer with --assume; see the questions below)")
    if f.note:
        lines.append(f"      note: {f.note}")
    for e in f.evidence:
        lines.append(f"      {e['serial']}: {_ev(e)}")
    lines.append(f"      {f.message}")
    if f.fix:
        k = f.fix["kind"]
        if k == "copy":
            src = f.fix["source"] or "(choose with --copy-from SERIAL)"
            lines.append(f"      fix: copy {', '.join(f.fix['fields'])} from {src} to {', '.join(f.fix['targets'])}"
                         + ("; set the LithiumBattery flag" if f.fix.get("bit_edits") else ""))
        elif k == "values":
            need = ", ".join(f"{nv['field']} (now {nv['current']:g} {nv['unit']}, schema {nv['schema_min']:g} to {nv['schema_max']:g})"
                             if isinstance(nv["current"], float) else nv["field"] for nv in f.fix["needs_value"])
            lines.append(f"      fix: enter {need} with --set FIELD=VALUE"
                         + ("; also " + ", ".join(f"{e['field']}={e['value']}" for e in f.fix.get("edits", [])) if f.fix.get("edits") else "")
                         + ("; set the LithiumBattery flag" if f.fix.get("bit_edits") else ""))
        elif k == "gui":
            lines.append(f"      fix: not by file here. {f.fix['text']}")
    return "\n".join(lines)


def render(report: Report) -> str:
    out = []
    for fr in report.files:
        out.append(f"{fr.name}: status {fr.status}" + (f"; {fr.message}" if fr.status != "ok" else "")
                   + (f"; {len(fr.serials)} inverter(s) {', '.join(fr.serials)}; {fr.nominal_voltage} V system; chemistry {fr.chemistry}"
                      + (f" ({fr.chemistry_source})" if fr.chemistry != "unknown" else "") if fr.status == "ok" else "")
                   + ("" if fr.editable else f"; the writer refuses this file: {fr.refusal_reason}" if fr.status == "ok" else ""))
        if fr.status == "ok" and not fr.findings:
            out.append("  no findings from the Phase 0 rules (D1, D2, C1, V1, V2, E1, E2)")
        for f in fr.findings:                 # already sorted by severity, rule, serial in the engine
            out.append(render_finding(f))
        out.append("")
    qs = report.questions
    if qs:
        out.append("Questions the file cannot answer (findings marked conditional depend on them):")
        for q in qs:
            out.append(f"  {q.id}: {q.text}  [affects {', '.join(q.affects)}]")
        out.append("")
    if report.intent:
        out.append(f"Intent recorded: {len(report.intent.get('edits', []))} value edit(s), {len(report.intent.get('bit_edits', []))} bit edit(s).")
    out.append("Findings are observations with evidence, not verdicts. Evidence classes: device-confirmed = a before/after on hardware; "
               "vendor-documented = a Victron citation; inferred = a corpus or forensic pattern. Decode confidence is the weakest field read.")
    return "\n".join(out)
