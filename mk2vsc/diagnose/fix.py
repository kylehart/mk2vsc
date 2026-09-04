"""Turn accepted findings into one corrected file through the writer's guards, and record the intent."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .report import FileReport
from ..fields import lookup
from ..writer import set_settings, set_bits, WriteRefused


class FixRefused(RuntimeError):
    """A fix cannot be built as asked: missing value, missing copy source, or not a by-file fix."""


def plan_edits(report: FileReport, accept: List[str], values: Optional[Dict[str, object]] = None,
               copy_from: Optional[str] = None) -> Tuple[List[dict], List[dict]]:
    """``(edits, bit_edits)`` for the accepted findings, or FixRefused naming what is missing."""
    ctx = report._ctx
    values = {lookup(k).name: v for k, v in (values or {}).items()}
    edits: Dict[Tuple[str, str], dict] = {}
    bits: Dict[Tuple[str, str, int], dict] = {}
    by_id = {f.id: f for f in report.findings}
    for fid in accept:
        f = by_id.get(fid)
        if f is None:
            raise FixRefused(f"no finding {fid!r} in this report")
        fix = f.fix
        if not fix:
            raise FixRefused(f"{fid}: nothing to apply")
        if fix["kind"] == "gui":
            raise FixRefused(f"{fid}: no by-file fix; {fix['text']}")
        if fix["kind"] == "copy":
            source = fix["source"] or copy_from
            if source is None:
                raise FixRefused(f"{fid}: choose the source inverter (--copy-from SERIAL); candidates {fix['candidates']}")
            if source not in fix["candidates"]:
                raise FixRefused(f"{fid}: {source} is not one of {fix['candidates']}")
            for t in fix["targets"]:
                if t == source:
                    continue
                for name in fix["fields"]:
                    edits[(t, name)] = {"serial": t, "field": name, "value": ctx.value(source, name)}
            if ctx.lithium_flag(source):
                for t in fix["targets"]:
                    if t != source and not ctx.lithium_flag(t):
                        bits[(t, "flags2", 4)] = {"serial": t, "field": "flags2", "bit": 4, "set": True}
        elif fix["kind"] == "values":
            missing = [nv["field"] for nv in fix["needs_value"] if nv["field"] not in values]
            if missing:
                raise FixRefused(f"{fid}: enter a value for {', '.join(missing)} (--set FIELD=VALUE); no generic template is offered")
            for nv in fix["needs_value"]:
                edits[(nv["serial"], nv["field"])] = {"serial": nv["serial"], "field": nv["field"], "value": values[nv["field"]]}
            for e in fix.get("edits", []):
                edits[(e["serial"], e["field"])] = dict(e)
        for b in fix.get("bit_edits", []):
            bits[(b["serial"], b["field"], b["bit"])] = dict(b)
    return list(edits.values()), list(bits.values())


def apply_fixes(data: bytes, report: FileReport, accept: List[str], values: Optional[Dict[str, object]] = None,
                copy_from: Optional[str] = None) -> Tuple[bytes, dict]:
    """The corrected bytes and the intent ``{"edits": [...], "bit_edits": [...]}`` that verify/check take."""
    if not report.editable:
        raise FixRefused(f"the writer refuses this file: {report.refusal_reason}")
    edits, bits = plan_edits(report, accept, values, copy_from)
    if not edits and not bits:
        raise FixRefused("nothing to change")
    out = data
    try:
        if edits:
            out, _ = set_settings(out, [(e["serial"], e["field"], e["value"]) for e in edits])
        if bits:
            out, _ = set_bits(out, [(b["serial"], b["field"], b["bit"], b["set"]) for b in bits])
    except WriteRefused as e:
        raise FixRefused(str(e))
    return out, {"edits": edits, "bit_edits": bits}
