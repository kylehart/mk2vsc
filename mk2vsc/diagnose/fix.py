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
    owner: Dict[Tuple[str, str], str] = {}          # which finding first claimed (serial, field)
    by_id = {f.id: f for f in report.findings}

    def put(key, rec, fid):
        prev = edits.get(key)
        if prev is not None and prev["value"] != rec["value"]:
            raise FixRefused(f"{fid} and {owner[key]} both change {key[1]} on {key[0]} to different values "
                             f"({rec['value']} vs {prev['value']}); accept one of them, or set the value explicitly")
        edits[key] = rec
        owner.setdefault(key, fid)

    for fid in accept:
        f = by_id.get(fid)
        if f is None:
            raise FixRefused(f"no finding {fid!r} in this report")
        fix = f.fix
        if not fix:
            raise FixRefused(f"{fid}: nothing to apply")
        if fix["kind"] == "gui":
            raise FixRefused(f"{fid}: no by-file fix; {fix['text']}")
        # the gate the finding itself declares: a conditional fix needs its question answered first
        unanswered = [q for q in f.conditional if not _answered(ctx, q)]
        if unanswered:
            raise FixRefused(f"{fid} is conditional on {', '.join(unanswered)}; answer with --assume "
                             + " ".join(_hint(q) for q in unanswered) + " before applying it")
        if fix["kind"] == "copy":
            source = copy_from or fix["source"]          # an explicit choice beats the rule's automatic source
            if source is None:
                raise FixRefused(f"{fid}: choose the source inverter (--copy-from SERIAL); candidates {fix['candidates']}")
            if source not in fix["candidates"]:
                raise FixRefused(f"{fid}: {source} is not one of {fix['candidates']}")
            targets = sorted({*fix["targets"], *fix["candidates"]} - {source})   # an overriding source becomes a target itself
            for t in targets:
                for name in fix["fields"]:
                    put((t, name), {"serial": t, "field": name, "value": ctx.value(source, name)}, fid)
                # the LithiumBattery flag follows the source in both directions
                if ctx.lithium_flag(t) != ctx.lithium_flag(source):
                    bits[(t, "flags2", 4)] = {"serial": t, "field": "flags2", "bit": 4, "set": ctx.lithium_flag(source)}
        elif fix["kind"] == "values":
            missing = [nv["field"] for nv in fix["needs_value"] if nv["field"] not in values]
            if missing:
                raise FixRefused(f"{fid}: enter a value for {', '.join(missing)} (--set FIELD=VALUE); no generic template is offered")
            for nv in fix["needs_value"]:
                put((nv["serial"], nv["field"]), {"serial": nv["serial"], "field": nv["field"], "value": values[nv["field"]]}, fid)
            for e in fix.get("edits", []):
                put((e["serial"], e["field"]), dict(e), fid)
            for b in fix.get("bit_edits", []):          # a copy derives its bit edits from the actual source above
                key = (b["serial"], b["field"], b["bit"])
                if key in bits and bits[key]["set"] != b["set"]:
                    raise FixRefused(f"{fid}: conflicting bit edits for {b['field']} bit {b['bit']} on {b['serial']}")
                bits[key] = dict(b)
    return list(edits.values()), list(bits.values())


def _answered(ctx, question: str) -> bool:
    if question == "chemistry":
        return ctx.chemistry != "unknown"
    if question == "shared_battery":
        return ctx.shared_battery is True
    if question == "ess_intended":
        return ctx.ess_intended is not None
    return False


def _hint(question: str) -> str:
    return {"chemistry": "chemistry=lithium|lead-acid", "shared_battery": "shared_battery=yes",
            "ess_intended": "ess_intended=yes|no"}.get(question, question)


def dry_run(data: bytes, report: FileReport, accept: List[str], values: Optional[Dict[str, object]] = None,
            copy_from: Optional[str] = None) -> dict:
    """The intent the writer would accept, without keeping the bytes: what ``--sheet`` prints.  Refuses exactly
    what ``apply_fixes`` refuses, so a sheet never asks a human to type a value the writer would not write."""
    _, intent = apply_fixes(data, report, accept, values, copy_from)
    return intent


def intent_for_check(intent: dict, corrected: bytes) -> dict:
    """The same intent in the form ``mk2vsc check --intent`` reads (mk2vsc.qualify.Intent): expected values per
    field, and the serials, read from the corrected file's final state.  A field is listed only when every inverter
    holds the same value after the fix (a per-inverter edit that leaves a peer different is not expressible there);
    bit edits are not expressible and are listed under ``bit_edits`` for the reader."""
    from ..sections import RvmsFile
    from ..units import units_by_serial
    units = units_by_serial(RvmsFile.parse(corrected))
    settings = {}
    for name in sorted({e["field"] for e in intent.get("edits", [])}):
        f = lookup(name)
        finals = {f.decode(u.setting(f.id)) for u in units.values()}
        if len(finals) == 1:
            settings[name] = finals.pop()
    return {"settings": settings, "serials": sorted(units), "require_agreement": True,
            "edits": intent.get("edits", []), "bit_edits": intent.get("bit_edits", [])}


def apply_fixes(data: bytes, report: FileReport, accept: List[str], values: Optional[Dict[str, object]] = None,
                copy_from: Optional[str] = None) -> Tuple[bytes, dict]:
    """The corrected bytes and the intent ``{"edits": [...], "bit_edits": [...]}`` a verify step compares against.
    ``intent_for_check`` turns it into the file ``mk2vsc check --intent`` reads."""
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
